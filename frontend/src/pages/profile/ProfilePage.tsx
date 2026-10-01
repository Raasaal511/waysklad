import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import {
  confirmTelegramLink,
  startTelegramLink,
  updateShop,
  changePassword,
  logoutAll,
} from '../../entities/profile/api'
import type { TelegramStart } from '../../entities/auth/api'
import { TelegramVerify } from '../../widgets/telegram-verify/TelegramVerify'
import type { Role } from '../../entities/auth/api'
import type { Tenant, UpdateShopInput } from '../../entities/profile/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useTheme, type AccentColor } from '../../app/ThemeContext'
import { useShop } from '../../app/ShopContext'
import { useCatalog } from '../../app/CatalogContext'
import { Modal } from '../../shared/ui/Modal'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { IconBrandTelegram, IconCheck, IconBuildingWarehouse, IconChevronRight } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { AppInstallCard } from './AppInstallCard'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ProfilePage.module.css'

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Владелец',
  manager: 'Управляющий',
  seller: 'Продавец',
  storekeeper: 'Кладовщик',
  analyst: 'Аналитик',
}

type Tab = 'personalization' | 'account' | 'connections'

/** Вкладка из ссылки (?tab=…): так неактивный пункт «Витрина» открывает сразу нужную. */
function tabFromQuery(value: string | null, canManageSettings: boolean): Tab | null {
  if (value === 'account') return 'account'
  if ((value === 'personalization' || value === 'connections') && canManageSettings) return value
  return null
}

export function ProfilePage() {
  const { user } = useAuth()
  const canManageSettings = user?.role === 'owner'
  const [searchParams] = useSearchParams()
  const queryTab = tabFromQuery(searchParams.get('tab'), canManageSettings)
  const [tab, setTab] = useState<Tab>(queryTab ?? 'account')

  // Повторный переход по ссылке, когда профиль уже открыт, тоже переключает вкладку.
  useEffect(() => {
    if (queryTab) setTab(queryTab)
  }, [queryTab])

  const TABS: { id: Tab; label: string }[] = [
    { id: 'account', label: 'Аккаунт' },
    ...(canManageSettings ? [{ id: 'personalization' as const, label: 'Персонализация' }] : []),
    ...(canManageSettings ? [{ id: 'connections' as const, label: 'Подключения' }] : []),
  ]

  return (
    <div className={layoutStyles.stack}>
      <h2>Профиль</h2>

      <div className={styles.tabs}>
        {TABS.map((t) => (
          <Button
            key={t.id}
            variant={tab === t.id ? 'primary' : 'secondary'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {tab === 'personalization' && canManageSettings && <PersonalizationTab />}
      {tab === 'account' && <AccountTab />}
      {tab === 'connections' && canManageSettings && <ConnectionsTab />}
    </div>
  )
}

function PersonalizationTab() {
  const { shop, setShop, setShopName } = useShop()
  const [name, setName] = useState(shop?.name ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // shop грузится один раз в ShopProvider при старте приложения — если эта
  // вкладка открылась раньше, чем ответ пришёл, просто ждём его, не запуская
  // свой собственный запрос
  useEffect(() => {
    if (shop) setName(shop.name)
  }, [shop])

  // Автосохранение с debounce вместо кнопки "Сохранить" — не шлём запрос на
  // каждую нажатую клавишу, ждём паузу в наборе, как в поиске по товарам.
  useEffect(() => {
    if (!shop) return
    const trimmed = name.trim()
    if (trimmed === shop.name) return
    if (!trimmed) return
    const timer = setTimeout(async () => {
      setError(null)
      setSaved(false)
      setSaving(true)
      try {
        const updated = await updateShop({ name: trimmed })
        setShop(updated)
        setShopName(updated.name)
        setSaved(true)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Не удалось сохранить')
      } finally {
        setSaving(false)
      }
    }, 600)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, shop?.name])

  useEffect(() => {
    if (!saved) return
    const timer = setTimeout(() => setSaved(false), 2500)
    return () => clearTimeout(timer)
  }, [saved])

  if (!shop) return <p className={layoutStyles.textMuted}>Загрузка…</p>

  return (
    <div className={layoutStyles.stack}>
      <ThemeSettings />

      <div className={[layoutStyles.stack, layoutStyles.card, layoutStyles.cardFull].join(' ')}>
        <div>
          <h3>Название магазина</h3>
          <p className={layoutStyles.textMuted}>Видно вам и сотрудникам в шапке интерфейса.</p>
        </div>
        <label className={[layoutStyles.field, styles.shopNameField].join(' ')}>
          Название
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </label>
        <div className={styles.shopNameStatus}>
          {saving && <span className={layoutStyles.textMuted}>Сохранение…</span>}
          {!saving && saved && !error && (
            <span className={layoutStyles.row} style={{ gap: 6 }}>
              <IconCheck size={16} stroke={1.8} className={styles.iconAccent} /> Сохранено
            </span>
          )}
          {error && <span className={layoutStyles.textDanger}>{error}</span>}
        </div>
      </div>

      <StorefrontSettings shop={shop} />
    </div>
  )
}

function StorefrontSettings({ shop }: { shop: Tenant }) {
  const { setShop } = useShop()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const storeUrl = shop.slug ? `${window.location.origin}/store/${shop.slug}` : null
  const { hash, key } = useLocation()
  const cardRef = useRef<HTMLDivElement>(null)
  const [highlighted, setHighlighted] = useState(false)

  // Пришли из меню по ссылке …#storefront — показываем, где включается витрина.
  useEffect(() => {
    if (hash !== '#storefront') return
    cardRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    setHighlighted(true)
    const timer = setTimeout(() => setHighlighted(false), 1600)
    return () => clearTimeout(timer)
  }, [hash, key])

  async function handleToggle(enabled: boolean) {
    setError(null)
    setSaving(true)
    try {
      const updated = await updateShop({ name: shop.name, storefront_enabled: enabled })
      setShop(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      ref={cardRef}
      id="storefront"
      className={[
        layoutStyles.stack,
        layoutStyles.card,
        layoutStyles.cardFull,
        styles.storefrontCard,
        highlighted && styles.storefrontCardHighlighted,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div>
        <h3>Публичная витрина</h3>
        <p className={layoutStyles.textMuted}>
          Включение, товары и заявки — в отдельном разделе меню.
        </p>
      </div>
      <label className="sale-checkbox">
        <input
          type="checkbox"
          checked={shop.storefront_enabled}
          disabled={saving}
          onChange={(e) => handleToggle(e.target.checked)}
        />
        Онлайн-витрина
      </label>
      <p className={layoutStyles.textMuted} style={{ margin: '-6px 0 0', fontSize: 13, lineHeight: 1.4 }}>
        Бета: каталог магазина по публичной ссылке
      </p>
      {error && <span className={layoutStyles.textDanger}>{error}</span>}
      {shop.storefront_enabled && (
        <div className={layoutStyles.row} style={{ gap: 8, flexWrap: 'wrap' }}>
          <Link to="/storefront">
            <Button>Открыть раздел «Витрина»</Button>
          </Link>
          {storeUrl && (
            <a href={storeUrl} target="_blank" rel="noreferrer" className={styles.storefrontLink}>
              {storeUrl}
            </a>
          )}
        </div>
      )}
    </div>
  )
}

const ACCENT_OPTIONS: { id: AccentColor; label: string; swatch: string }[] = [
  { id: 'green', label: 'Зелёный', swatch: '#1f5c3f' },
  { id: 'blue', label: 'Синий', swatch: '#2456a6' },
  { id: 'terracotta', label: 'Терракотовый', swatch: '#b5502e' },
  { id: 'violet', label: 'Фиолетовый', swatch: '#5b3f9e' },
]

function ThemeSettings() {
  const { mode, accent, setMode, setAccent } = useTheme()

  return (
    <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
      <div>
        <h3>Оформление</h3>
        <p className={layoutStyles.textMuted}>
          Тема и акцентный цвет интерфейса — видно только вам на этом устройстве.
        </p>
      </div>

      <div className={layoutStyles.stack} style={{ gap: 8 }}>
        <span className="field-label">Тема</span>
        <div className={layoutStyles.row}>
          <Button variant={mode === 'light' ? 'primary' : 'secondary'} onClick={() => setMode('light')}>
            Светлая
          </Button>
          <Button variant={mode === 'dark' ? 'primary' : 'secondary'} onClick={() => setMode('dark')}>
            Тёмная
          </Button>
        </div>
      </div>

      <div className={layoutStyles.stack} style={{ gap: 8 }}>
        <span className="field-label">Акцентный цвет</span>
        <div className={[layoutStyles.row, layoutStyles.wrap].join(' ')}>
          {ACCENT_OPTIONS.map((opt) => (
            <Button
              key={opt.id}
              variant={accent === opt.id ? 'primary' : 'secondary'}
              onClick={() => setAccent(opt.id)}
              style={accent === opt.id ? undefined : { color: 'var(--text)' }}
            >
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  background: opt.swatch,
                }}
              />
              {opt.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}

function AccountTab() {
  const { user, logout } = useAuth()
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [showLogoutAllConfirm, setShowLogoutAllConfirm] = useState(false)

  async function handleLogoutAll() {
    try {
      await logoutAll()
    } finally {
      // токен этого устройства тоже отозван запросом выше — выходим и локально
      logout()
    }
  }

  return (
    <div className={layoutStyles.stack}>
      <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
        <div className={[layoutStyles.row, layoutStyles.between].join(' ')}>
          <div className={layoutStyles.stack} style={{ gap: 2 }}>
            <span className={layoutStyles.textMuted}>Вы вошли как</span>
            <strong>
              {user?.name} — {user ? ROLE_LABELS[user.role] : ''}
            </strong>
          </div>
          <Button variant="secondary" className={styles.accountAction} onClick={() => setShowPasswordForm(true)}>
            Сменить пароль
          </Button>
        </div>
        <div className={[layoutStyles.row, layoutStyles.between].join(' ')}>
          <div className={layoutStyles.stack} style={{ gap: 2 }}>
            <span className={layoutStyles.textMuted}>Завершить все сессии</span>
            <span className={layoutStyles.textMuted}>
              Выйти на всех устройствах, включая текущее
            </span>
          </div>
          <Button variant="secondary" className={styles.accountAction} onClick={() => setShowLogoutAllConfirm(true)}>
            Выйти везде
          </Button>
        </div>
      </div>

      <AppInstallCard />

      {showPasswordForm && (
        <Modal title="Сменить пароль" onClose={() => setShowPasswordForm(false)}>
          <ChangePasswordForm onDone={() => setShowPasswordForm(false)} />
        </Modal>
      )}

      {showLogoutAllConfirm && (
        <ConfirmDialog
          title="Выйти на всех устройствах?"
          message="Все сессии, включая текущую, будут завершены — понадобится войти заново."
          confirmLabel="Выйти везде"
          danger
          onConfirm={handleLogoutAll}
          onClose={() => setShowLogoutAllConfirm(false)}
        />
      )}

      <MyWarehouses />
    </div>
  )
}

function MyWarehouses() {
  const { warehouses, stock, ensureWarehouses, ensureStock } = useCatalog()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([ensureWarehouses(), ensureStock()])
      .catch(() => {})
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) return null
  if (warehouses.length === 0) return null

  const itemCount = (warehouseId: number) => stock.filter((s) => s.warehouse_id === warehouseId).length

  return (
    <div className={layoutStyles.stack}>
      <h3>Ваши склады</h3>
      <div className={layoutStyles.warehouseTiles}>
        {warehouses.map((w) => (
          <Link key={w.id} to={`/stock/${w.id}`} className={layoutStyles.warehouseTile}>
            <div className={layoutStyles.warehouseTileHeader}>
              <span className={layoutStyles.warehouseTileIcon}>
                <IconBuildingWarehouse size={26} stroke={1.6} />
              </span>
              <div className={layoutStyles.warehouseTileHeading}>
                <strong className={layoutStyles.warehouseTileName}>{w.name}</strong>
                <span className={layoutStyles.textMuted}>{w.address || 'Без адреса'}</span>
              </div>
              <IconChevronRight size={20} stroke={1.8} className={layoutStyles.warehouseTileChevron} />
            </div>
            <div className={layoutStyles.warehouseTileStats}>
              <div className={layoutStyles.stat}>
                <span className={layoutStyles.statLabel}>Позиций</span>
                <span className={layoutStyles.statValue}>{itemCount(w.id)}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

function ConnectionsTab() {
  return (
    <div className={layoutStyles.stack}>
      <TelegramSettings />
    </div>
  )
}

function TelegramSettings() {
  const { shop, setShop } = useShop()
  const [link, setLink] = useState<TelegramStart | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loading = shop === null
  const connected = Boolean(shop?.owner_telegram_chat_id)

  async function startLink() {
    setError(null)
    setStarting(true)
    try {
      setLink(await startTelegramLink())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось начать подключение')
    } finally {
      setStarting(false)
    }
  }

  async function confirm(code: string) {
    if (!link) return
    setShop(await confirmTelegramLink(link.token, code))
    setLink(null)
  }

  return (
    <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
      <div className={[layoutStyles.row, layoutStyles.between].join(' ')}>
        <div>
          <h3>Telegram</h3>
          <p className={layoutStyles.textMuted}>
            Новые заявки с витрины, напоминания о долгах и вечерняя сводка с файлом Excel.
          </p>
        </div>
        {!loading && (
          <span className={`badge${connected ? ' accent' : ''}`}>{connected ? 'Подключён' : 'Не подключён'}</span>
        )}
      </div>

      {!loading && !connected && (
        <p className={styles.telegramWarning} role="status">
          Уведомления сейчас никуда не уходят: Telegram не подключён.
        </p>
      )}
      {error && <p className={layoutStyles.error}>{error}</p>}
      {!loading && (
        <Button
          variant={connected ? 'secondary' : 'primary'}
          className={styles.telegramAction}
          onClick={startLink}
          disabled={starting}
        >
          <IconBrandTelegram size={20} stroke={1.8} />
          {starting ? 'Готовим ссылку…' : connected ? 'Подключить другой Telegram' : 'Подключить Telegram'}
        </Button>
      )}

      {!loading && shop && (
        <SummaryScheduleSettings shop={shop} onSaved={setShop} disabled={!connected} />
      )}

      {link && (
        <Modal title="Подключение Telegram" onClose={() => setLink(null)}>
          <TelegramVerify
            start={link}
            onConfirm={confirm}
            onRestart={startLink}
            restartLabel="Получить новую ссылку"
            lead="Бот проверит, что номер ваш, и сюда начнут приходить заявки и сводки."
          />
        </Modal>
      )}
    </div>
  )
}

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, h) => ({
  value: String(h),
  label: `${String(h).padStart(2, '0')}:00 по Москве`,
}))

function SummaryScheduleSettings({
  shop,
  onSaved,
  disabled = false,
}: {
  shop: Tenant
  onSaved: (shop: Tenant) => void
  /** Пока chat_id не подключён — расписание видно, но менять нельзя. */
  disabled?: boolean
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function toggle(patch: Partial<UpdateShopInput>) {
    if (disabled) return
    setError(null)
    setSaving(true)
    try {
      const updated = await updateShop({ name: shop.name, ...patch })
      onSaved(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить настройки')
    } finally {
      setSaving(false)
    }
  }

  const locked = disabled || saving

  return (
    <div className={[layoutStyles.stack, styles.summarySchedule].join(' ')}>
      <span className={layoutStyles.fieldLabel}>Когда присылать сводку</span>
      {disabled && (
        <p className={layoutStyles.textMuted}>
          Сначала подключите Telegram — иначе расписание не сработает.
        </p>
      )}

      <div className={styles.summaryRow}>
        <label className={styles.summaryCheckbox}>
          <input
            type="checkbox"
            checked={shop.summary_daily_enabled}
            disabled={locked}
            onChange={(e) => toggle({ summary_daily_enabled: e.target.checked })}
          />
          Ежедневно
        </label>
        {shop.summary_daily_enabled && (
          <Select
            className={styles.summaryHourSelect}
            value={String(shop.summary_daily_hour_msk)}
            onChange={(v) => toggle({ summary_daily_hour_msk: Number(v) })}
            options={HOUR_OPTIONS}
            disabled={locked}
          />
        )}
      </div>

      <label className={styles.summaryCheckbox}>
        <input
          type="checkbox"
          checked={shop.summary_weekly_enabled}
          disabled={locked}
          onChange={(e) => toggle({ summary_weekly_enabled: e.target.checked })}
        />
        Еженедельно, по воскресеньям
      </label>

      <label className={styles.summaryCheckbox}>
        <input
          type="checkbox"
          checked={shop.summary_monthly_enabled}
          disabled={locked}
          onChange={(e) => toggle({ summary_monthly_enabled: e.target.checked })}
        />
        Ежемесячно, в последний день месяца
      </label>

      {error && <p className={layoutStyles.error}>{error}</p>}
    </div>
  )
}

function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const { login } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (newPassword !== confirmPassword) {
      setError('Новый пароль и подтверждение не совпадают')
      return
    }
    setSaving(true)
    try {
      // смена пароля отзывает прежний токен (token_version) — сохраняем
      // новый, иначе следующий же запрос разлогинит пользователя
      const result = await changePassword({ current_password: currentPassword, new_password: newPassword })
      login(result)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сменить пароль')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Текущий пароль
        <input
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </label>
      <label className={layoutStyles.field}>
        Новый пароль
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={6}
        />
      </label>
      <label className={layoutStyles.field}>
        Повторите новый пароль
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          minLength={6}
        />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сменить пароль'}
      </Button>
    </form>
  )
}

