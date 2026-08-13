import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { connectTelegram, getShop, updateShop, changePassword } from '../../entities/profile/api'
import type { Role } from '../../entities/auth/api'
import type { Tenant } from '../../entities/profile/api'
import { listWarehouses, listStock, type Warehouse, type StockItem } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useTheme, type AccentColor } from '../../app/ThemeContext'
import { useShop } from '../../app/ShopContext'
import { Modal } from '../../shared/ui/Modal'
import { IconCheck, IconBuildingWarehouse, IconChevronRight, IconPencil } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'

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
    <div className="stack">
      <h2>Профиль</h2>

      <div className="row tabs">
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

  if (loading) return <p className="text-muted">Загрузка…</p>

  return (
    <div className="stack">
      <ThemeSettings />

      <form className="form card card-full" onSubmit={handleSubmit}>
        <div>
          <h3>Название магазина</h3>
          <p className="text-muted">Видно вам и сотрудникам в шапке интерфейса.</p>
        </div>
        <label className="field">
          Название
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </label>
        {error && <p className="error">{error}</p>}
        {saved && !error && (
          <p className="row" style={{ gap: 6 }}>
            <IconCheck size={16} stroke={1.8} className="icon-accent" /> Сохранено
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
    <div className="card card-full stack">
      <div>
        <h3>Оформление</h3>
        <p className="text-muted">Тема и акцентный цвет интерфейса — видно только вам на этом устройстве.</p>
      </div>

      <div className="stack" style={{ gap: 8 }}>
        <span className="field-label">Тема</span>
        <div className="row">
          <Button variant={mode === 'light' ? 'primary' : 'secondary'} onClick={() => setMode('light')}>
            Светлая
          </Button>
          <Button variant={mode === 'dark' ? 'primary' : 'secondary'} onClick={() => setMode('dark')}>
            Тёмная
          </Button>
        </div>
      </div>

      <div className="stack" style={{ gap: 8 }}>
        <span className="field-label">Акцентный цвет</span>
        <div className="row wrap">
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
    <div className="stack">
      <div className="card card-full stack">
        <div className="row between">
          <div className="stack" style={{ gap: 2 }}>
            <span className="text-muted">Вы вошли как</span>
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
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([listWarehouses(), listStock()])
      .then(([w, s]) => {
        setWarehouses(w)
        setStock(s)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return null
  if (warehouses.length === 0) return null

  const itemCount = (warehouseId: number) => stock.filter((s) => s.warehouse_id === warehouseId).length

  return (
    <div className="stack">
      <h3>Ваши склады</h3>
      <div className="warehouse-grid">
        {warehouses.map((w) => (
          <Link key={w.id} to={`/stock/${w.id}`} className="card warehouse-card">
            <div className="row between">
              <div className="row" style={{ gap: 10 }}>
                <span className="warehouse-card-icon">
                  <IconBuildingWarehouse size={18} stroke={1.8} />
                </span>
                <strong>{w.name}</strong>
              </div>
              <IconChevronRight size={18} stroke={1.8} />
            </div>
            {w.address && <span className="text-muted">{w.address}</span>}
            <span className="badge accent">{itemCount(w.id)} позиций</span>
          </Link>
        ))}
      </div>
    </div>
  )
}

function ConnectionsTab() {
  return (
    <div className="stack">
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
    <div className="card card-full stack">
      <div className="row between">
        <div>
          <h3>Telegram-сводка</h3>
          <p className="text-muted">
            Каждый вечер бот присылает продажи, выручку, прибыль и суммы, выданные в долг.
          </p>
        </div>
        {!loading && (
          <span className={`badge ${connectedChatId ? 'accent' : ''}`}>
            {connectedChatId ? 'Подключено' : 'Не подключено'}
          </span>
        )}
      </div>

      {!loading && connectedChatId && (
        <div className="row between">
          <span className="row" style={{ gap: 6 }}>
            <IconCheck size={16} stroke={1.8} className="icon-accent" />
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
    <div className="stack">
      <div className="stack telegram-steps">
        <div className="row telegram-step">
          <span className="telegram-step-number">1</span>
          <span>
            Откройте бота{' '}
            <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer">
              @userinfobot
            </a>{' '}
            в Telegram и нажмите «Start»
          </span>
        </div>
        <div className="row telegram-step">
          <span className="telegram-step-number">2</span>
          <span>Скопируйте число из поля «Id» в его ответе</span>
        </div>
        <div className="row telegram-step">
          <span className="telegram-step-number">3</span>
          <span>Вставьте это число ниже и нажмите «Подключить»</span>
        </div>
      </div>

      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          Telegram chat_id
          <input value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="123456789" required />
        </label>
        {error && <p className="error">{error}</p>}
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
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Текущий пароль
        <input
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </label>
      <label className="field">
        Новый пароль
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={6}
        />
      </label>
      <label className="field">
        Повторите новый пароль
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          minLength={6}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сменить пароль'}
      </Button>
    </form>
  )
}

