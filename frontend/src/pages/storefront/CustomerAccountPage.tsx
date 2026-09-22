import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { IconCheck, IconChevronDown, IconChevronRight, IconLogout } from '@tabler/icons-react'
import {
  changeCustomerPassword,
  clearCustomerToken,
  getCustomerProfile,
  listMyStorefrontRequests,
  loadCustomerToken,
  logoutCustomerEverywhere,
  requestCustomerPhoneCode,
  saveCustomerToken,
  updateCustomerProfile,
  verifyCustomerPhoneCode,
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
import { notifyCustomerAuthChanged } from './CustomerLoginModal'
import styles from './CustomerAccountPage.module.css'

const STATUS_LABEL: Record<MyRequest['status'], string> = {
  new: 'Новый',
  accepted: 'Подтверждён',
  rejected: 'Отклонён',
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

function OrderCard({ req, currentSlug }: { req: MyRequest; currentSlug: string }) {
  const [open, setOpen] = useState(false)
  const total =
    req.status === 'accepted' && req.accepted_total != null
      ? req.accepted_total
      : req.order_total
  const inThisShop = req.shop_slug === currentSlug

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
            {!inThisShop && req.shop_slug && (
              <Link to={`/store/${req.shop_slug}`} className={styles.textLink}>
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
 * Профиль покупателя внутри магазина: данные, заказы этого магазина,
 * свёрнутый блок заказов в других, избранное, безопасность.
 */
export function CustomerAccountPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const shopName = peekCachedStorefrontShopProfile(slug)?.name

  const [token, setToken] = useState(() => loadCustomerToken())
  const [profile, setProfile] = useState<CustomerProfile | null>(null)
  const [orders, setOrders] = useState<MyRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [othersOpen, setOthersOpen] = useState(false)

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
    const title = shopName ? `${shopName} — Профиль` : 'Профиль'
    setPageMeta({ title })
    return () => resetPageMeta()
  }, [shopName])

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
        const [me, reqs] = await Promise.all([
          getCustomerProfile(),
          listMyStorefrontRequests({ limit: 100 }),
        ])
        if (cancelled) return
        setProfile(me)
        setOrders(reqs.items)
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

  const { here, others } = useMemo(() => {
    const hereList: MyRequest[] = []
    const otherList: MyRequest[] = []
    for (const o of orders) {
      if (o.shop_slug === slug) hereList.push(o)
      else otherList.push(o)
    }
    return { here: hereList, others: otherList }
  }, [orders, slug])

  if (!token) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/store/${slug}/login?next=${next}`} replace />
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
      {shopName && (
        <p className={styles.subtitle}>в магазине «{shopName}»</p>
      )}

      {loading && <p className={styles.muted}>Загрузка…</p>}
      {error && (
        <EmptyState
          title="Не удалось загрузить"
          description={error}
          actionLabel="Повторить"
          onAction={() => setToken(loadCustomerToken())}
        />
      )}

      {!loading && !error && profile && (
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
                    <button type="button" className={styles.textBtn} onClick={() => {
                      setVerifyOpen(true)
                      setVerifyStep('send')
                      setVerifyError(null)
                    }}>
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
              {[formatSince(profile.created_at), `Заказов: ${profile.stats.requests_total}, активных: ${profile.stats.requests_active}`]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Мои заказы</h2>
            {here.length === 0 ? (
              <EmptyState
                illustration="empty-archive"
                title="Здесь появятся ваши заказы"
                description={shopName ? `в магазине «${shopName}»` : undefined}
                actionLabel="Перейти к покупкам"
                onAction={() => navigate(`/store/${slug}`)}
              />
            ) : (
              <ul className={styles.orderList}>
                {here.map((req) => (
                  <OrderCard key={req.id} req={req} currentSlug={slug} />
                ))}
              </ul>
            )}

            {others.length > 0 && (
              <div className={styles.others}>
                <button
                  type="button"
                  className={styles.othersToggle}
                  onClick={() => setOthersOpen((v) => !v)}
                  aria-expanded={othersOpen}
                >
                  {othersOpen ? <IconChevronDown size={18} /> : <IconChevronRight size={18} />}
                  Заказы в других магазинах ({others.length})
                </button>
                {othersOpen && (
                  <ul className={styles.orderList}>
                    {others.map((req) => (
                      <OrderCard key={req.id} req={req} currentSlug={slug} />
                    ))}
                  </ul>
                )}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <Link to={`/store/${slug}/favorites`} className={styles.navRow}>
              Избранное
              <IconChevronRight size={18} />
            </Link>
          </section>

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

      {verifyOpen && (
        <Modal title="Подтверждение телефона" onClose={() => setVerifyOpen(false)}>
          {verifyStep === 'send' && (
            <div className={styles.modalBody}>
              <p className={styles.muted}>Отправим код в Telegram</p>
              {verifyError && <p className={styles.error}>{verifyError}</p>}
              <Button type="button" onClick={sendCode}>
                Отправить код
              </Button>
            </div>
          )}
          {verifyStep === 'bot' && (
            <div className={styles.modalBody}>
              <p>Откройте бота и нажмите Старт — после этого запросите код снова.</p>
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
