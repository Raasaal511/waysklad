import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  IconCheck,
  IconChevronRight,
  IconLogout,
  IconMessage,
} from '@tabler/icons-react'
import {
  changeCustomerPassword,
  clearCustomerToken,
  countUnreadCustomerChats,
  getCustomerProfile,
  isCustomerChatUnread,
  listCustomerChats,
  listMyStorefrontRequests,
  loadCustomerToken,
  logoutCustomerEverywhere,
  requestCustomerPhoneCode,
  saveCustomerToken,
  updateCustomerProfile,
  verifyCustomerPhoneCode,
  type CustomerChatSummary,
  type CustomerProfile,
  type MyRequest,
} from '../../entities/auth/customerApi'
import { peekCachedStorefrontShopProfile } from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { Button } from '../../shared/ui/Button'
import { EmptyState } from '../../shared/ui/EmptyState'
import { Modal } from '../../shared/ui/Modal'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { loadLastStoreSlug } from '../../shared/lib/lastStore'
import { notifyCustomerAuthChanged } from './customerAuthEvents'
import styles from './CustomerAccountPage.module.css'

const STATUS_LABEL: Record<MyRequest['status'], string> = {
  new: 'Новый',
  accepted: 'Подтверждён',
  rejected: 'Отклонён',
}

type Tab = 'overview' | 'orders' | 'chats' | 'reviews' | 'shops'

function tabFromPath(pathname: string): Tab {
  if (pathname.includes('/account/orders')) return 'orders'
  if (pathname.includes('/account/chats')) return 'chats'
  if (pathname.includes('/account/reviews')) return 'reviews'
  if (pathname.includes('/account/shops')) return 'shops'
  return 'overview'
}

function formatSince(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ]
  return `С ${months[d.getMonth()]} ${d.getFullYear()}`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function OrderCard({ req }: { req: MyRequest }) {
  const [open, setOpen] = useState(false)
  const total =
    req.status === 'accepted' && req.accepted_total != null
      ? req.accepted_total
      : req.order_total
  const shopSlug = req.shop_slug

  return (
    <li className={styles.orderCard}>
      <button type="button" className={styles.orderHead} onClick={() => setOpen((v) => !v)}>
        <span className={styles.orderShop}>
          {req.shop_logo ? (
            <img src={req.shop_logo} alt="" width={36} height={36} className={styles.orderLogo} />
          ) : (
            <span className={styles.orderLogoFallback} aria-hidden="true">
              {req.shop_name.charAt(0)}
            </span>
          )}
          <span>
            <strong>{req.shop_name}</strong>
            <span className={styles.orderMeta}>
              {formatDate(req.created_at)}
              {total ? ` · ${formatMoney(total)}` : ''}
            </span>
          </span>
        </span>
        <span className={styles.orderStatus} data-status={req.status}>
          {STATUS_LABEL[req.status]}
        </span>
      </button>
      {open && (
        <div className={styles.orderBody}>
          <ul className={styles.orderLines}>
            {req.order_lines.map((line) => (
              <li key={`${line.product_id}-${line.name}`}>
                {line.name} × {line.quantity}
              </li>
            ))}
          </ul>
          {req.status === 'accepted' && req.due_date && (
            <p className={styles.muted}>
              Готово к {req.due_date}
              {req.to_pay ? ` · к оплате ${formatMoney(req.to_pay)}` : ''}
            </p>
          )}
          <div className={styles.orderActions}>
            {shopSlug && (
              <Link to={`/account/chats/${req.id}`} className={styles.textLink}>
                Чат с магазином
              </Link>
            )}
            {shopSlug && (
              <Link to={`/store/${shopSlug}`} className={styles.textLink}>
                В магазин «{req.shop_name}»
              </Link>
            )}
          </div>
        </div>
      )}
    </li>
  )
}

/**
 * Общий кабинет покупателя (/account): данные, заказы, чаты, отзывы, витрины.
 */
export function CustomerAccountPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const tab = tabFromPath(location.pathname)
  const lastSlug = loadLastStoreSlug()

  const [token, setToken] = useState(() => loadCustomerToken())
  const [profile, setProfile] = useState<CustomerProfile | null>(null)
  const [orders, setOrders] = useState<MyRequest[]>([])
  const [chats, setChats] = useState<CustomerChatSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editPhone, setEditPhone] = useState('')
  const [editError, setEditError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [verifyOpen, setVerifyOpen] = useState(false)
  const [verifyStep, setVerifyStep] = useState<'send' | 'bot' | 'code'>('send')
  const [verifyCode, setVerifyCode] = useState('')
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [botLink, setBotLink] = useState('')
  const [retryAfter, setRetryAfter] = useState(0)

  const [passwordOpen, setPasswordOpen] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)

  useEffect(() => {
    setPageMeta({ title: 'Профиль' })
    return () => resetPageMeta()
  }, [])

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [me, reqs, chatList] = await Promise.all([
          getCustomerProfile(),
          listMyStorefrontRequests({ limit: 100 }),
          listCustomerChats().catch(() => [] as CustomerChatSummary[]),
        ])
        if (cancelled) return
        setProfile(me)
        setOrders(reqs.items)
        setChats(chatList)
        setEditName(me.name)
        setEditPhone(me.phone)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearCustomerToken()
          notifyCustomerAuthChanged()
          setToken(null)
          return
        }
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить профиль')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (retryAfter <= 0) return
    const t = setTimeout(() => setRetryAfter((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [retryAfter])

  const unreadCount = useMemo(() => countUnreadCustomerChats(chats), [chats])

  const shops = useMemo(() => {
    const map = new Map<string, { slug: string; name: string; logo: string; orders: number }>()
    for (const o of orders) {
      if (!o.shop_slug) continue
      const cur = map.get(o.shop_slug)
      if (cur) cur.orders += 1
      else map.set(o.shop_slug, { slug: o.shop_slug, name: o.shop_name, logo: o.shop_logo, orders: 1 })
    }
    for (const c of chats) {
      if (!c.shop_slug || map.has(c.shop_slug)) continue
      map.set(c.shop_slug, { slug: c.shop_slug, name: c.shop_name, logo: c.shop_logo, orders: 0 })
    }
    if (lastSlug && !map.has(lastSlug)) {
      const cached = peekCachedStorefrontShopProfile(lastSlug)
      map.set(lastSlug, {
        slug: lastSlug,
        name: cached?.name ?? lastSlug,
        logo: cached?.logo ?? '',
        orders: 0,
      })
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  }, [orders, chats, lastSlug])

  const reviewables = useMemo(() => {
    const map = new Map<string, { productId: number; name: string; photo: string; requestId: number; shopSlug: string }>()
    for (const req of orders) {
      if (req.status !== 'accepted') continue
      for (const line of req.order_lines) {
        const key = `${req.shop_slug}:${line.product_id}`
        if (!map.has(key)) {
          map.set(key, {
            productId: line.product_id,
            name: line.name,
            photo: line.photo,
            shopSlug: req.shop_slug,
            requestId: req.id,
          })
        }
      }
    }
    return [...map.values()]
  }, [orders])

  if (!token) {
    const next = encodeURIComponent(location.pathname + location.search)
    const loginSlug = lastSlug || 'waysklad'
    return <Navigate to={`/store/${loginSlug}/login?next=${next}`} replace />
  }

  async function saveProfile(e: FormEvent) {
    e.preventDefault()
    setEditError(null)
    setSaving(true)
    try {
      const phoneChanged = editPhone.trim() !== (profile?.phone ?? '')
      const updated = await updateCustomerProfile({
        name: editName.trim(),
        phone: phoneChanged ? editPhone.trim() : undefined,
      })
      setProfile((p) =>
        p
          ? {
              ...p,
              name: updated.name,
              phone: updated.phone,
              phone_verified: updated.phone_verified,
              username: updated.username,
            }
          : p,
      )
      setEditing(false)
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  async function sendCode() {
    setVerifyError(null)
    try {
      const res = await requestCustomerPhoneCode()
      setRetryAfter(res.retry_after)
      if (res.telegram_deep_link) {
        setBotLink(res.telegram_deep_link)
        setVerifyStep('bot')
      } else {
        setVerifyStep('code')
      }
    } catch (err) {
      setVerifyError(err instanceof ApiError ? err.message : 'Не удалось отправить код')
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault()
    setVerifyError(null)
    try {
      const res = await verifyCustomerPhoneCode(verifyCode.trim())
      setProfile((p) =>
        p
          ? {
              ...p,
              phone_verified: res.phone_verified,
              phone_verified_at: res.phone_verified_at,
            }
          : p,
      )
      setVerifyOpen(false)
      setVerifyCode('')
      setVerifyStep('send')
    } catch (err) {
      setVerifyError(err instanceof ApiError ? err.message : 'Неверный код')
    }
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault()
    setPasswordError(null)
    try {
      const res = await changeCustomerPassword({
        new_password: newPassword,
        current_password: profile?.has_password ? currentPassword : undefined,
      })
      saveCustomerToken(res.access_token)
      notifyCustomerAuthChanged()
      setPasswordOpen(false)
      setCurrentPassword('')
      setNewPassword('')
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : 'Не удалось сменить пароль')
    }
  }

  function logout() {
    clearCustomerToken()
    notifyCustomerAuthChanged()
    setToken(null)
  }

  async function logoutAll() {
    if (!window.confirm('Выйти на всех устройствах?')) return
    try {
      await logoutCustomerEverywhere()
    } catch {
      /* токен всё равно сбрасываем локально */
    }
    logout()
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Профиль</h1>
      <p className={styles.subtitle}>личный кабинет покупателя</p>

      <nav className={styles.tabs} aria-label="Разделы профиля">
        <NavLink
          to="/account"
          end
          className={({ isActive }) => `${styles.tab} ${isActive || tab === 'overview' ? styles.tabActive : ''}`}
        >
          Обзор
        </NavLink>
        <NavLink
          to="/account/orders"
          className={({ isActive }) => `${styles.tab} ${isActive ? styles.tabActive : ''}`}
        >
          Заказы
          {orders.length > 0 && <span className={styles.tabCount}>{orders.length}</span>}
        </NavLink>
        <NavLink
          to="/account/chats"
          className={({ isActive }) => `${styles.tab} ${isActive ? styles.tabActive : ''}`}
        >
          Чаты
          {unreadCount > 0 && <span className={styles.tabBadge}>{unreadCount}</span>}
        </NavLink>
        <NavLink
          to="/account/reviews"
          className={({ isActive }) => `${styles.tab} ${isActive ? styles.tabActive : ''}`}
        >
          Отзывы
        </NavLink>
        <NavLink
          to="/account/shops"
          className={({ isActive }) => `${styles.tab} ${isActive ? styles.tabActive : ''}`}
        >
          Витрины
          {shops.length > 0 && <span className={styles.tabCount}>{shops.length}</span>}
        </NavLink>
      </nav>

      {loading && <p className={styles.muted}>Загрузка…</p>}
      {error && (
        <EmptyState
          title="Не удалось загрузить"
          description={error}
          actionLabel="Повторить"
          onAction={() => setToken(loadCustomerToken())}
        />
      )}

      {!loading && !error && profile && tab === 'overview' && (
        <>
          <section className={styles.card}>
            <div className={styles.profileRow}>
              <span className={styles.avatar} aria-hidden="true">
                {(profile.name || '?').charAt(0).toUpperCase()}
              </span>
              <div className={styles.profileInfo}>
                <strong className={styles.profileName}>{profile.name || 'Без имени'}</strong>
                {profile.username && <span className={styles.muted}>@{profile.username}</span>}
                <span className={styles.phoneLine}>{profile.phone}</span>
                {profile.phone_verified ? (
                  <span className={styles.verified}>
                    <IconCheck size={14} stroke={2} /> Телефон подтверждён
                  </span>
                ) : (
                  <span className={styles.unverified}>
                    Телефон не подтверждён
                    <button
                      type="button"
                      className={styles.textBtn}
                      onClick={() => {
                        setVerifyOpen(true)
                        setVerifyStep('send')
                        setVerifyError(null)
                      }}
                    >
                      Подтвердить
                    </button>
                  </span>
                )}
              </div>
              <Button variant="secondary" type="button" onClick={() => setEditing((v) => !v)}>
                {editing ? 'Отмена' : 'Изменить'}
              </Button>
            </div>

            {editing && (
              <form className={styles.editForm} onSubmit={saveProfile}>
                <label className={styles.field}>
                  Имя
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    required
                    maxLength={200}
                  />
                </label>
                <label className={styles.field}>
                  Телефон
                  <PhoneInput value={editPhone} onChange={setEditPhone} />
                </label>
                {editPhone.trim() !== profile.phone && (
                  <p className={styles.warn}>
                    При смене телефона подтверждение сбросится — номер нужно будет подтвердить снова.
                  </p>
                )}
                {editError && <p className={styles.error}>{editError}</p>}
                <Button type="submit" disabled={saving}>
                  {saving ? 'Сохранение…' : 'Сохранить'}
                </Button>
              </form>
            )}

            <p className={styles.stats}>
              {[
                formatSince(profile.created_at),
                `Заказов: ${profile.stats.requests_total}, активных: ${profile.stats.requests_active}`,
                profile.stats.shops_count ? `Витрин: ${profile.stats.shops_count}` : '',
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </section>

          {unreadCount > 0 && (
            <section className={styles.notice}>
              <IconMessage size={18} stroke={1.8} />
              <div>
                <strong>Магазин ответил</strong>
                <p className={styles.muted}>
                  {unreadCount === 1
                    ? 'Есть новое сообщение в чате'
                    : `Новых сообщений: ${unreadCount}`}
                </p>
              </div>
              <Link to="/account/chats" className={styles.textLink}>
                Открыть
              </Link>
            </section>
          )}

          {shops.length > 0 && (
            <section className={styles.section}>
              <Link to="/account/shops" className={styles.navRow}>
                Мои витрины ({shops.length})
                <IconChevronRight size={18} />
              </Link>
            </section>
          )}

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Настройки</h2>
            <button type="button" className={styles.navRow} onClick={() => setPasswordOpen(true)}>
              {profile.has_password ? 'Сменить пароль' : 'Задать пароль'}
              <IconChevronRight size={18} />
            </button>
            <button type="button" className={styles.navRow} onClick={logout}>
              Выйти
              <IconLogout size={18} />
            </button>
            <button type="button" className={`${styles.navRow} ${styles.dangerRow}`} onClick={logoutAll}>
              Выйти на всех устройствах
              <IconLogout size={18} />
            </button>
          </section>
        </>
      )}

      {!loading && !error && profile && tab === 'orders' && (
        <section className={styles.section} id="orders">
          <h2 className={styles.sectionTitle}>Мои заказы</h2>
          {orders.length === 0 ? (
            <EmptyState
              illustration="empty-archive"
              title="Здесь появятся ваши заказы"
              description="Оформите заказ в любом магазине — он отобразится здесь."
              actionLabel={lastSlug ? 'К последней витрине' : 'К витринам'}
              onAction={() => navigate(lastSlug ? `/store/${lastSlug}` : '/account/shops')}
            />
          ) : (
            <ul className={styles.orderList}>
              {orders.map((req) => (
                <OrderCard key={req.id} req={req} />
              ))}
            </ul>
          )}
        </section>
      )}

      {!loading && !error && profile && tab === 'chats' && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Чаты</h2>
          {chats.length === 0 ? (
            <EmptyState
              title="Пока нет переписки"
              description="Напишите магазину из заказа — диалог появится здесь."
              actionLabel="К заказам"
              onAction={() => navigate('/account/orders')}
            />
          ) : (
            <ul className={styles.chatList}>
              {chats.map((chat) => {
                const unread = isCustomerChatUnread(chat)
                return (
                  <li key={chat.request_id}>
                    <Link
                      to={`/account/chats/${chat.request_id}`}
                      className={`${styles.chatRow} ${unread ? styles.chatRowUnread : ''}`}
                    >
                      <span className={styles.chatMain}>
                        <strong>
                          {chat.shop_name || `Заказ #${chat.request_id}`}
                          {unread && <span className={styles.dot} aria-label="Новое сообщение" />}
                        </strong>
                        <span className={styles.chatPreview}>
                          {chat.last_message_from_shop ? 'Магазин: ' : 'Вы: '}
                          {chat.last_message}
                        </span>
                      </span>
                      <span className={styles.chatMeta}>
                        {formatDate(chat.last_message_at)}
                        <IconChevronRight size={16} />
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      )}

      {!loading && !error && profile && tab === 'reviews' && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Отзывы</h2>
          <p className={styles.muted}>
            Отзыв можно оставить на товары из подтверждённых заказов.
          </p>
          {reviewables.length === 0 ? (
            <EmptyState
              illustration="empty-reviews"
              title="Пока нечего оценивать"
              description="Когда магазин подтвердит заказ, товары появятся здесь."
              actionLabel="К заказам"
              onAction={() => navigate('/account/orders')}
            />
          ) : (
            <ul className={styles.reviewList}>
              {reviewables.map((item) => (
                <li key={`${item.shopSlug}-${item.productId}`} className={styles.reviewRow}>
                  {item.photo ? (
                    <img src={item.photo} alt="" className={styles.reviewPhoto} width={48} height={48} />
                  ) : (
                    <span className={styles.reviewPhotoFallback} aria-hidden="true" />
                  )}
                  <span className={styles.reviewName}>{item.name}</span>
                  <Link
                    to={`/store/${item.shopSlug}/products/${item.productId}?writeReview=1#reviews`}
                    className={styles.textLink}
                  >
                    Написать отзыв
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {!loading && !error && profile && tab === 'shops' && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Витрины</h2>
          <p className={styles.muted}>Магазины, где вы заказывали или которые недавно открывали.</p>
          {shops.length === 0 ? (
            <EmptyState
              title="Пока нет витрин"
              description="Откройте магазин по ссылке продавца — он появится здесь."
            />
          ) : (
            <ul className={styles.shopList}>
              {shops.map((shop) => (
                <li key={shop.slug}>
                  <Link to={`/store/${shop.slug}`} className={styles.shopRow}>
                    {shop.logo ? (
                      <img src={shop.logo} alt="" className={styles.shopLogo} width={40} height={40} />
                    ) : (
                      <span className={styles.shopLogoFallback} aria-hidden="true">
                        {shop.name.charAt(0)}
                      </span>
                    )}
                    <span className={styles.shopMain}>
                      <strong>{shop.name}</strong>
                      <span className={styles.muted}>
                        /store/{shop.slug}
                        {shop.orders > 0 ? ` · заказов: ${shop.orders}` : ''}
                      </span>
                    </span>
                    <IconChevronRight size={18} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {verifyOpen && (
        <Modal title="Подтверждение телефона" onClose={() => setVerifyOpen(false)}>
          {verifyStep === 'send' && (
            <div className={styles.modalBody}>
              <p className={styles.muted}>
                Отправим код в Telegram. Можно ввести его здесь или командой{' '}
                <code>/confirm 123456</code> в боте.
              </p>
              {verifyError && <p className={styles.error}>{verifyError}</p>}
              <Button type="button" onClick={sendCode}>
                Отправить код
              </Button>
            </div>
          )}
          {verifyStep === 'bot' && (
            <div className={styles.modalBody}>
              <p>
                Откройте бота и нажмите «Старт» — после этого запросите код снова. Позже код можно
                подтвердить командой <code>/confirm</code>.
              </p>
              {botLink && (
                <a href={botLink} target="_blank" rel="noreferrer" className={styles.textLink}>
                  Открыть бота
                </a>
              )}
              {verifyError && <p className={styles.error}>{verifyError}</p>}
              <Button type="button" onClick={sendCode} disabled={retryAfter > 0}>
                {retryAfter > 0 ? `Повторить через ${retryAfter} с` : 'Код отправлен? Запросить снова'}
              </Button>
            </div>
          )}
          {verifyStep === 'code' && (
            <form className={styles.modalBody} onSubmit={submitCode}>
              <label className={styles.field}>
                Код из Telegram
                <input
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  required
                  minLength={6}
                />
              </label>
              <p className={styles.muted}>
                Или отправьте боту: <code>/confirm {verifyCode || '123456'}</code>
              </p>
              {verifyError && <p className={styles.error}>{verifyError}</p>}
              <Button type="submit">Подтвердить</Button>
              <button
                type="button"
                className={styles.textBtn}
                disabled={retryAfter > 0}
                onClick={sendCode}
              >
                {retryAfter > 0 ? `Отправить повторно через ${retryAfter} с` : 'Отправить код ещё раз'}
              </button>
            </form>
          )}
        </Modal>
      )}

      {passwordOpen && (
        <Modal
          title={profile?.has_password ? 'Сменить пароль' : 'Задать пароль'}
          onClose={() => setPasswordOpen(false)}
        >
          <form className={styles.modalBody} onSubmit={submitPassword}>
            {profile?.has_password && (
              <label className={styles.field}>
                Текущий пароль
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </label>
            )}
            <label className={styles.field}>
              Новый пароль
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </label>
            {passwordError && <p className={styles.error}>{passwordError}</p>}
            <Button type="submit">Сохранить</Button>
          </form>
        </Modal>
      )}
    </div>
  )
}
