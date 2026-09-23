import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  searchClients,
  createClient,
  createSupplier,
  type Client,
  type Supplier,
} from '../../entities/counterparty/api'
import { listSupplierDebts, type Debt } from '../../entities/debt/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus, IconChevronRight, IconUser, IconTruck, IconPhone, IconMapPin } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { EmptyState } from '../../shared/ui/EmptyState'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { useCatalog } from '../../app/CatalogContext'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ClientsPage.module.css'

const TAB_KEY = 'clients_tab'

export function ClientsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const highlightId = searchParams.get('highlight')
  const { suppliers, ensureSuppliers, refresh: refreshCatalog } = useCatalog()
  const [tab, setTab] = useState<'clients' | 'suppliers'>(
    () => (localStorage.getItem(TAB_KEY) === 'suppliers' ? 'suppliers' : 'clients'),
  )

  useEffect(() => {
    localStorage.setItem(TAB_KEY, tab)
  }, [tab])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null)
  const highlightRef = useRef<HTMLButtonElement>(null)

  async function load() {
    setLoading(true)
    try {
      const c = await searchClients('', true)
      setClients(c)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить контрагентов')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    ensureSuppliers().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!loading && highlightId) {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [loading, highlightId])

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Контрагенты</h2>
        <div className={layoutStyles.pageTitleActions}>
          <div className={layoutStyles.pageTitleActionsDesktop}>
            <Button onClick={() => setShowForm(true)}>
              <IconPlus size={16} stroke={1.8} /> {tab === 'clients' ? 'Клиент' : 'Поставщик'}
            </Button>
          </div>
          <div className={layoutStyles.pageTitleActionsMobile}>
            <IconButton
              variant="accent"
              size="lg"
              aria-label={tab === 'clients' ? 'Добавить клиента' : 'Добавить поставщика'}
              onClick={() => setShowForm(true)}
            >
              <IconPlus size={20} stroke={2} />
            </IconButton>
          </div>
        </div>
      </div>

      <div className="sale-period-tabs">
        <Button variant="secondary" active={tab === 'clients'} onClick={() => setTab('clients')}>
          Клиенты
        </Button>
        <Button variant="secondary" active={tab === 'suppliers'} onClick={() => setTab('suppliers')}>
          Поставщики
        </Button>
      </div>

      {showForm && tab === 'clients' && (
        <Modal title="Новый клиент" onClose={() => setShowForm(false)}>
          <NewClientForm
            onDone={() => {
              setShowForm(false)
              load()
            }}
          />
        </Modal>
      )}
      {showForm && tab === 'suppliers' && (
        <Modal title="Новый поставщик" onClose={() => setShowForm(false)}>
          <NewSupplierForm
            onDone={() => {
              setShowForm(false)
              refreshCatalog(['suppliers'])
            }}
          />
        </Modal>
      )}

      {selectedSupplier && (
        <Modal title={selectedSupplier.name} onClose={() => setSelectedSupplier(null)}>
          <SupplierDebtsSummary supplier={selectedSupplier} />
        </Modal>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : tab === 'clients' ? (
        clients.length === 0 ? (
          <EmptyState
            illustration="empty-clients"
            title="Клиентов пока нет"
            description="Добавьте клиента, чтобы продавать в долг и вести историю."
            actionLabel="Добавить клиента"
            onAction={() => setShowForm(true)}
          />
        ) : (
          <div className={styles['contact-row-list']}>
            {clients.map((c, i) => (
              <button
                key={c.id}
                type="button"
                ref={String(c.id) === highlightId ? highlightRef : undefined}
                className={[
                  styles['contact-row'],
                  'sale-history-row-in',
                  String(c.id) === highlightId && styles['row-highlight'],
                ].filter(Boolean).join(' ')}
                style={{ '--row-delay': `${Math.min(i, 12) * 25}ms` } as CSSProperties}
                onClick={() => navigate(`/clients/${c.id}`)}
              >
                <span className={styles['contact-row-icon']}>
                  <IconUser size={16} stroke={1.8} />
                </span>
                <div className={styles['contact-row-main']}>
                  <div className={styles['contact-row-top']}>
                    <span className={styles['contact-row-name']}>{c.name}</span>
                    {!c.is_active && <span className="badge">Неактивен</span>}
                  </div>
                  <div className={styles['contact-row-meta']}>
                    {c.phone && (
                      <span>
                        <IconPhone size={13} stroke={1.8} /> {c.phone}
                      </span>
                    )}
                    {c.city && (
                      <span>
                        <IconMapPin size={13} stroke={1.8} /> {c.city}
                      </span>
                    )}
                    {c.debt_limit && <span>Лимит долга: {formatMoney(c.debt_limit)} ₽</span>}
                  </div>
                </div>
                <IconChevronRight size={18} stroke={1.8} className={styles['contact-row-chevron']} />
              </button>
            ))}
          </div>
        )
      ) : suppliers.length === 0 ? (
        <EmptyState
          illustration="empty-clients"
          title="Поставщиков пока нет"
          description="Добавьте поставщика, чтобы принимать товар и вести закупки."
          actionLabel="Добавить поставщика"
          onAction={() => setShowForm(true)}
        />
      ) : (
        <div className={styles['contact-row-list']}>
          {suppliers.map((s, i) => (
            <button
              key={s.id}
              type="button"
              className={`${styles['contact-row']} sale-history-row-in`}
              style={{ '--row-delay': `${Math.min(i, 12) * 25}ms` } as CSSProperties}
              onClick={() => setSelectedSupplier(s)}
            >
              <span className={styles['contact-row-icon']}>
                <IconTruck size={16} stroke={1.8} />
              </span>
              <div className={styles['contact-row-main']}>
                <div className={styles['contact-row-top']}>
                  <span className={styles['contact-row-name']}>{s.name}</span>
                </div>
                {s.contact && <div className={styles['contact-row-meta']}>{s.contact}</div>}
              </div>
              <IconChevronRight size={18} stroke={1.8} className={styles['contact-row-chevron']} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function SupplierDebtsSummary({ supplier }: { supplier: Supplier }) {
  const [debts, setDebts] = useState<Debt[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSupplierDebts(supplier.id)
      .then((summary) => setDebts(summary.debts))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги'))
  }, [supplier.id])

  const active = debts?.filter((d) => !d.is_closed) ?? []
  const closed = debts?.filter((d) => d.is_closed) ?? []
  const totalBalance = active.reduce((sum, d) => sum + Number(d.balance), 0)

  return (
    <div className={layoutStyles.stack}>
      <div className={`${layoutStyles.row} ${layoutStyles.wrap}`} style={{ gap: 12 }}>
        {supplier.contact && <span className={layoutStyles.textMuted}>{supplier.contact}</span>}
        {supplier.note && <span className={layoutStyles.textMuted}>{supplier.note}</span>}
      </div>

      <h3>Долги (мы должны)</h3>
      {error && <p className={layoutStyles.error}>{error}</p>}
      {debts === null ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : debts.length === 0 ? (
        <p className={layoutStyles.textMuted}>Долгов нет</p>
      ) : (
        <div className={layoutStyles.stack} style={{ gap: 8 }}>
          {active.length > 0 && (
            <p className={layoutStyles.textMuted}>Активных долгов на {formatMoney(totalBalance)} ₽</p>
          )}
          {[...active, ...closed].map((d) => (
            <div key={d.id} className={styles['client-debt-item']}>
              <span className={DEBT_STATUS_BADGE_CLASS[d.status]}>{DEBT_STATUS_LABELS[d.status]}</span>
              <span>{formatMoney(d.balance)} ₽ из {formatMoney(d.amount)} ₽</span>
              {d.due_date && (
                <span className={layoutStyles.textMuted}>до {new Date(d.due_date).toLocaleDateString('ru-RU')}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function NewClientForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [city, setCity] = useState('')
  const [debtLimit, setDebtLimit] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createClient({ name, phone, city, debt_limit: debtLimit || null })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить клиента')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Имя
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className={layoutStyles.field}>
        Телефон
        <PhoneInput value={phone} onChange={setPhone} />
      </label>
      <label className={layoutStyles.field}>
        Город
        <input value={city} onChange={(e) => setCity(e.target.value)} />
      </label>
      <label className={layoutStyles.field}>
        Лимит долга
        <input
          type="text"
          inputMode="decimal"
          value={debtLimit}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setDebtLimit(normalized)
          }}
        />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить клиента'}
      </Button>
    </form>
  )
}

function NewSupplierForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('')
  const [contact, setContact] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createSupplier({ name, contact })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить поставщика')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className={layoutStyles.field}>
        Контакт
        <input value={contact} onChange={(e) => setContact(e.target.value)} />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить поставщика'}
      </Button>
    </form>
  )
}
