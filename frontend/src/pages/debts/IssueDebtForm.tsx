import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import {
  issueDebt,
  issueSupplierDebt,
  createInstallment,
  repayDebt,
} from '../../entities/debt/api'
import { type Client, type Supplier } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import {
  type InstallmentPeriod,
  INSTALLMENT_PERIOD_OPTIONS,
  buildInstallmentSchedule,
  estimatePartsCount,
} from '../../entities/debt/installmentSchedule'
import { ApiError } from '../../shared/api/client'
import {
  IconPlus,
  IconUser,
  IconTruck,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { QuickNewClientForm } from '../../shared/ui/QuickNewClientForm'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from '../products/ProductDetailPage.module.css'
import styles from './IssueDebtForm.module.css'

const DUE_DATE_PRESETS: { label: string; days: number }[] = [
  { label: 'Неделя', days: 7 },
  { label: '2 мес.', days: 60 },
  { label: '3 мес.', days: 90 },
  { label: '4 мес.', days: 120 },
  { label: 'Полгода', days: 182 },
  { label: 'Год', days: 365 },
]

function addDays(days: number) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function DueDatePresets({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className={styles.dueDatePresets}>
      {DUE_DATE_PRESETS.map((p) => {
        const presetValue = addDays(p.days)
        return (
          <button
            key={p.label}
            type="button"
            className={[styles.dueDatePreset, value === presetValue && styles.dueDatePresetActive]
              .filter(Boolean)
              .join(' ')}
            onClick={() => onChange(presetValue)}
          >
            {p.label}
          </button>
        )
      })}
    </div>
  )
}

export function IssueDebtForm({
  clients,
  onClientCreated,
  suppliers,
  onDone,
}: {
  clients: Client[]
  onClientCreated: (client: Client) => void
  suppliers: Supplier[]
  onDone: (debtId?: number) => void
}) {
  const { warehouses, ensureWarehouses } = useCatalog()
  const [kind, setKind] = useState<'client' | 'supplier'>('client')
  const [clientId, setClientId] = useState<number | null>(clients[0]?.id ?? null)
  const [showNewClientForm, setShowNewClientForm] = useState(false)
  const [supplierId, setSupplierId] = useState<number | null>(suppliers[0]?.id ?? null)
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [withInstallment, setWithInstallment] = useState(false)
  const [downPayment, setDownPayment] = useState('')
  const [partsInput, setPartsInput] = useState('3')
  const [partsTouched, setPartsTouched] = useState(false)
  const parts = Math.min(Math.max(Number(partsInput) || 0, 1), 60)
  const [period, setPeriod] = useState<InstallmentPeriod>('month')
  const [firstPaymentDate, setFirstPaymentDate] = useState(new Date().toISOString().slice(0, 10))

  useEffect(() => {
    ensureWarehouses()
      .then(() => {})
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (warehouses.length > 0 && warehouseId == null) {
      setWarehouseId(warehouses[0].id)
    }
  }, [warehouses, warehouseId])

  // Пока пользователь не поправил «Платежей» руками, число платежей само
  // подстраивается под срок долга и периодичность — например, год с разбивкой
  // раз в месяц сразу даёт 12 платежей, а не дефолтные 3.
  useEffect(() => {
    if (!withInstallment || partsTouched || !dueDate || !firstPaymentDate) return
    setPartsInput(String(estimatePartsCount(firstPaymentDate, dueDate, period)))
  }, [withInstallment, partsTouched, dueDate, firstPaymentDate, period])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const downPaymentNum = Number(downPayment || '0')
  const downPaymentInvalid = downPaymentNum < 0 || (amount !== '' && downPaymentNum >= Number(amount))
  const remainingAfterDownPayment = Math.max(Number(amount || '0') - downPaymentNum, 0).toFixed(2)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!dueDate) {
      setError('Укажите срок «Долг до»')
      return
    }
    if (warehouseId == null) {
      setError('Укажите склад')
      return
    }
    if (withInstallment && !firstPaymentDate) {
      setError('Укажите дату первого платежа рассрочки')
      return
    }
    if (withInstallment && downPaymentInvalid) {
      setError('Первый взнос должен быть меньше суммы долга')
      return
    }
    if (withInstallment && parts < 2) {
      setError('Платежей должно быть не меньше двух')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const debt =
        kind === 'client'
          ? clientId &&
            (await issueDebt({
              client_id: clientId,
              warehouse_id: warehouseId,
              amount,
              due_date: dueDate,
              note,
            }))
          : supplierId &&
            (await issueSupplierDebt({
              supplier_id: supplierId,
              warehouse_id: warehouseId,
              amount,
              due_date: dueDate,
              note,
            }))
      if (!debt) return
      if (withInstallment) {
        if (downPaymentNum > 0) {
          await repayDebt(debt.id, { amount: downPayment, paid_on: firstPaymentDate, note: 'Первый взнос' })
        }
        await createInstallment(
          debt.id,
          buildInstallmentSchedule(remainingAfterDownPayment, parts, firstPaymentDate, period),
        )
      }
      onDone(debt.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выдать долг')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <section
        className={`${detail.section} ${detail.reveal}`}
        style={{ '--reveal-delay': '0ms' } as CSSProperties}
      >
        <h3 className={detail.sectionTitle}>Кому</h3>
        <div className={styles.kindTabs}>
          <Button
            type="button"
            variant={kind === 'client' ? 'primary' : 'secondary'}
            onClick={() => setKind('client')}
          >
            <IconUser size={16} stroke={1.8} /> Клиенту (нам должны)
          </Button>
          <Button
            type="button"
            variant={kind === 'supplier' ? 'primary' : 'secondary'}
            onClick={() => setKind('supplier')}
          >
            <IconTruck size={16} stroke={1.8} /> Поставщику (мы должны)
          </Button>
        </div>

        {kind === 'client' ? (
          <label className={layoutStyles.field}>
            Клиент
            <div className="sale-client-row">
              <Select
                className="sale-client-select"
                value={clientId != null ? String(clientId) : ''}
                onChange={(v) => setClientId(Number(v))}
                options={clients.map((c) => ({ value: String(c.id), label: c.name }))}
              />
              <QuickNewClientForm
                open={showNewClientForm}
                onOpenChange={setShowNewClientForm}
                trigger={
                  <Button type="button" variant="secondary" onClick={() => setShowNewClientForm(true)}>
                    <IconPlus size={16} stroke={1.8} /> Клиент
                  </Button>
                }
                onCreated={(client) => {
                  onClientCreated(client)
                  setClientId(client.id)
                  setShowNewClientForm(false)
                }}
              />
            </div>
          </label>
        ) : (
          <label className={layoutStyles.field}>
            Поставщик
            <Select
              value={supplierId != null ? String(supplierId) : ''}
              onChange={(v) => setSupplierId(Number(v))}
              options={suppliers.map((s) => ({ value: String(s.id), label: s.name }))}
            />
          </label>
        )}

        {warehouses.length > 1 ? (
          <label className={layoutStyles.field}>
            Склад
            <Select
              value={warehouseId != null ? String(warehouseId) : ''}
              onChange={(v) => setWarehouseId(Number(v))}
              options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
            />
          </label>
        ) : warehouses.length === 1 ? (
          <p className={layoutStyles.textMuted} style={{ margin: 0, fontSize: 13 }}>
            Склад: {warehouses[0].name}
          </p>
        ) : null}
      </section>

      <section
        className={`${detail.section} ${detail.reveal}`}
        style={{ '--reveal-delay': '60ms' } as CSSProperties}
      >
        <h3 className={detail.sectionTitle}>Сумма и срок</h3>
        <label className={layoutStyles.field}>
          Сумма
          <input
            type="text"
            inputMode="decimal"
            value={amount}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setAmount(normalized)
            }}
            required
            autoFocus
          />
        </label>
        <label className={layoutStyles.field}>
          Долг до
          <DateInput
            value={dueDate}
            min={new Date().toISOString().slice(0, 10)}
            onChange={setDueDate}
            required
          />
        </label>
        <DueDatePresets value={dueDate} onChange={setDueDate} />
        <label className={layoutStyles.field}>
          Заметка
          <input value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
      </section>

      <section
        className={`${detail.section} ${detail.reveal}`}
        style={{ '--reveal-delay': '110ms' } as CSSProperties}
      >
        <h3 className={detail.sectionTitle}>Рассрочка</h3>
        <label className="sale-checkbox">
          <input
            type="checkbox"
            checked={withInstallment}
            onChange={(e) => {
              setWithInstallment(e.target.checked)
              if (!e.target.checked) setPartsTouched(false)
            }}
          />
          С рассрочкой
        </label>

        {withInstallment && (
          <div className={layoutStyles.stack} style={{ gap: 14 }}>
            <label className={layoutStyles.field}>
              Первый взнос (необязательно)
              <input
                type="text"
                inputMode="decimal"
                placeholder="0"
                value={downPayment}
                onChange={(e) => {
                  const normalized = normalizeDecimalInput(e.target.value)
                  if (normalized !== null) setDownPayment(normalized)
                }}
              />
            </label>
            {downPaymentNum > 0 && (
              <p className={downPaymentInvalid ? layoutStyles.error : layoutStyles.textMuted}>
                {downPaymentInvalid
                  ? 'Первый взнос должен быть меньше суммы долга'
                  : `В рассрочку пойдёт ${formatMoney(remainingAfterDownPayment)} ₽`}
              </p>
            )}
            <div className={layoutStyles.row}>
              <label className={layoutStyles.field} style={{ flex: 1 }}>
                Платежей
                <input
                  type="number"
                  min={2}
                  max={60}
                  value={partsInput}
                  onChange={(e) => {
                    setPartsInput(e.target.value.replace(/^0+(?=\d)/, ''))
                    setPartsTouched(true)
                  }}
                  onBlur={() => setPartsInput(String(parts))}
                />
              </label>
              <label className={layoutStyles.field} style={{ flex: 1 }}>
                Периодичность
                <Select
                  value={period}
                  onChange={(v) => setPeriod(v as InstallmentPeriod)}
                  options={INSTALLMENT_PERIOD_OPTIONS}
                />
              </label>
            </div>
            <label className={layoutStyles.field}>
              {downPaymentNum > 0 ? 'Дата первого взноса и старт графика' : 'Первый платёж'}
              <DateInput
                value={firstPaymentDate}
                min={new Date().toISOString().slice(0, 10)}
                onChange={setFirstPaymentDate}
              />
            </label>
          </div>
        )}
      </section>

      {error && <p className={layoutStyles.error}>{error}</p>}

      <div
        className={`${styles.saveBar} ${detail.reveal}`}
        style={{ '--reveal-delay': '160ms' } as CSSProperties}
      >
        <Button
          type="submit"
          disabled={
            saving ||
            (kind === 'client' ? !clientId : !supplierId) ||
            (withInstallment && downPaymentInvalid)
          }
        >
          {saving ? 'Сохранение…' : 'Выдать долг'}
        </Button>
      </div>
    </form>
  )
}
