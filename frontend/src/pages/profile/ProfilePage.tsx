import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { connectTelegram, getShop, updateShop, changePassword } from '../../entities/profile/api'
import type { Role } from '../../entities/auth/api'
import type { Tenant } from '../../entities/profile/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useTheme, type AccentColor } from '../../app/ThemeContext'
import { useShop } from '../../app/ShopContext'
import { useCatalog } from '../../app/CatalogContext'
import { Modal } from '../../shared/ui/Modal'
import { IconCheck, IconBuildingWarehouse, IconChevronRight, IconPencil } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
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

export function ProfilePage() {
  const { user } = useAuth()
  const canManageSettings = user?.role === 'owner'
  const [tab, setTab] = useState<Tab>('account')

  const TABS: { id: Tab; label: string }[] = [
    { id: 'account', label: 'Аккаунт' },
    ...(canManageSettings ? [{ id: 'personalization' as const, label: 'Персонализация' }] : []),
    ...(canManageSettings ? [{ id: 'connections' as const, label: 'Подключения' }] : []),
  ]

  return (
    <div className={layoutStyles.stack}>
      <h2>Профиль</h2>

      <div className={layoutStyles.row}>
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
  const { setShopName } = useShop()
  const [shop, setShop] = useState<Tenant | null>(null)
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getShop()
      .then((s) => {
        setShop(s)
        setName(s.name)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить магазин'))
      .finally(() => setLoading(false))
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    setSaving(true)
    try {
      const updated = await updateShop({ name })
      setShop(updated)
      setShopName(updated.name)
      setSaved(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className={layoutStyles.textMuted}>Загрузка…</p>

  return (
    <div className={layoutStyles.stack}>
      <ThemeSettings />

      <form
        className={[layoutStyles.form, layoutStyles.card, layoutStyles.cardFull].join(' ')}
        onSubmit={handleSubmit}
      >
        <div>
          <h3>Название магазина</h3>
          <p className={layoutStyles.textMuted}>Видно вам и сотрудникам в шапке интерфейса.</p>
        </div>
        <label className={layoutStyles.field}>
          Название
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        {saved && !error && (
          <p className={layoutStyles.row} style={{ gap: 6 }}>
            <IconCheck size={16} stroke={1.8} className={styles.iconAccent} /> Сохранено
          </p>
        )}
        <Button type="submit" disabled={saving || !shop}>
          {saving ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </form>
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
  const { user } = useAuth()
  const [showPasswordForm, setShowPasswordForm] = useState(false)

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
          <Button variant="secondary" onClick={() => setShowPasswordForm(true)}>
            Сменить пароль
          </Button>
        </div>
      </div>

      {showPasswordForm && (
        <Modal title="Сменить пароль" onClose={() => setShowPasswordForm(false)}>
          <ChangePasswordForm onDone={() => setShowPasswordForm(false)} />
        </Modal>
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
  const [connectedChatId, setConnectedChatId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  function load() {
    setLoading(true)
    getShop()
      .then((s) => setConnectedChatId(s.owner_telegram_chat_id))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
      <div className={[layoutStyles.row, layoutStyles.between].join(' ')}>
        <div>
          <h3>Telegram-сводка</h3>
          <p className={layoutStyles.textMuted}>
            Каждый вечер бот присылает продажи, выручку, прибыль и суммы, выданные в долг.
          </p>
        </div>
        {!loading && (
          <span className={`${layoutStyles.badge} ${connectedChatId ? layoutStyles.accent : ''}`}>
            {connectedChatId ? 'Подключено' : 'Не подключено'}
          </span>
        )}
      </div>

      {!loading && connectedChatId && (
        <div className={[layoutStyles.row, layoutStyles.between].join(' ')}>
          <span className={layoutStyles.row} style={{ gap: 6 }}>
            <IconCheck size={16} stroke={1.8} className={styles.iconAccent} />
            Chat ID: {connectedChatId}
          </span>
          <IconButton
            variant="muted"
            tooltip="Изменить"
            aria-label="Изменить подключение Telegram"
            onClick={() => setShowForm(true)}
          >
            <IconPencil size={16} stroke={1.8} />
          </IconButton>
        </div>
      )}

      {!loading && !connectedChatId && (
        <Button onClick={() => setShowForm(true)}>
          Подключить
        </Button>
      )}

      {showForm && (
        <Modal title="Telegram-сводка" onClose={() => setShowForm(false)}>
          <TelegramConnectForm
            onDone={() => {
              setShowForm(false)
              load()
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function TelegramConnectForm({ onDone }: { onDone: () => void }) {
  const [chatId, setChatId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await connectTelegram(chatId)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось подключить Telegram')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={layoutStyles.stack}>
      <div className={[layoutStyles.stack, styles.telegramSteps].join(' ')}>
        <div className={[layoutStyles.row, styles.telegramStep].join(' ')}>
          <span className={styles.telegramStepNumber}>1</span>
          <span>
            Откройте бота{' '}
            <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer">
              @userinfobot
            </a>{' '}
            в Telegram и нажмите «Start»
          </span>
        </div>
        <div className={[layoutStyles.row, styles.telegramStep].join(' ')}>
          <span className={styles.telegramStepNumber}>2</span>
          <span>Скопируйте число из поля «Id» в его ответе</span>
        </div>
        <div className={[layoutStyles.row, styles.telegramStep].join(' ')}>
          <span className={styles.telegramStepNumber}>3</span>
          <span>Вставьте это число ниже и нажмите «Подключить»</span>
        </div>
      </div>

      <form className={layoutStyles.form} onSubmit={handleSubmit}>
        <label className={layoutStyles.field}>
          Telegram chat_id
          <input value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="123456789" required />
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        <Button type="submit" disabled={saving}>
          {saving ? 'Сохранение…' : 'Подключить'}
        </Button>
      </form>
    </div>
  )
}

function ChangePasswordForm({ onDone }: { onDone: () => void }) {
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
      await changePassword({ current_password: currentPassword, new_password: newPassword })
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

