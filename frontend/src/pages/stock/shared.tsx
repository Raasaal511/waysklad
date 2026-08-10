import { useEffect, useState, type FormEvent } from 'react'
import {
  createWarehouse,
  receiveGoods,
  writeOff,
  transferStock,
  type Warehouse,
} from '../../entities/inventory/api'
import { type Product } from '../../entities/product/api'
import { listEmployees } from '../../entities/profile/api'
import type { User } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { normalizeDecimalInput } from '../../shared/lib/format'

export type MovementMode = 'receive' | 'write_off' | 'transfer'

export const MODE_LABELS: Record<MovementMode, string> = {
  receive: 'Приёмка',
  write_off: 'Списание',
  transfer: 'Перемещение',
}

/** Ответственным за склад может быть только владелец или кладовщик (storekeeper) — так же проверяется на бэкенде. */
export function useWarehouseManagerCandidates(): User[] {
  const { user } = useAuth()
  const [candidates, setCandidates] = useState<User[]>([])

  useEffect(() => {
    listEmployees()
      .then((employees) => {
        const list = employees.filter((e) => e.role === 'storekeeper' || e.role === 'owner')
        if (user && user.role === 'owner' && !list.some((e) => e.id === user.id)) {
          list.unshift(user)
        }
        setCandidates(list)
      })
      .catch(() => {})
  }, [user])

  return candidates
}

export function AssignedUsersField({
  candidates,
  selectedIds,
  onChange,
}: {
  candidates: User[]
  selectedIds: number[]
  onChange: (ids: number[]) => void
}) {
  function toggle(id: number) {
    onChange(
      selectedIds.includes(id) ? selectedIds.filter((v) => v !== id) : [...selectedIds, id],
    )
  }

  if (candidates.length === 0) {
    return (
      <p className="text-muted">
        Нет доступных ответственных — сначала добавьте кладовщика в «Профиль → Аккаунт → Сотрудники».
      </p>
    )
  }

  return (
    <div className="stack" style={{ gap: 8 }}>
      {candidates.map((c) => (
        <label key={c.id} className="row" style={{ gap: 8 }}>
          <input
            type="checkbox"
            checked={selectedIds.includes(c.id)}
            onChange={() => toggle(c.id)}
          />
          {c.name}
          {c.role === 'owner' && <span className="text-muted"> (владелец)</span>}
        </label>
      ))}
    </div>
  )
}

export function NewWarehouseForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [assignedIds, setAssignedIds] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const candidates = useWarehouseManagerCandidates()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createWarehouse({ name, address, assigned_user_ids: assignedIds })
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать склад')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Название склада
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Адрес
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      <label className="field">
        Ответственные за склад
        <AssignedUsersField
          candidates={candidates}
          selectedIds={assignedIds}
          onChange={setAssignedIds}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Создать склад'}
      </Button>
    </form>
  )
}

export function MovementForm({
  mode,
  products,
  warehouses,
  fixedWarehouseId,
  onDone,
}: {
  mode: MovementMode
  products: Product[]
  warehouses: Warehouse[]
  fixedWarehouseId?: number
  onDone: () => void
}) {
  const otherWarehouses = fixedWarehouseId
    ? warehouses.filter((w) => w.id !== fixedWarehouseId)
    : warehouses

  const [warehouseId, setWarehouseId] = useState<number | null>(
    fixedWarehouseId ?? warehouses[0]?.id ?? null,
  )
  const [toWarehouseId, setToWarehouseId] = useState<number | null>(otherWarehouses[0]?.id ?? null)
  const [productId, setProductId] = useState<number | null>(products[0]?.id ?? null)
  const [quantity, setQuantity] = useState('')
  const [cost, setCost] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!warehouseId || !productId) return
    setError(null)
    setSaving(true)
    try {
      if (mode === 'receive') {
        await receiveGoods({
          warehouse_id: warehouseId,
          lines: [{ product_id: productId, quantity, cost: cost || undefined }],
        })
      } else if (mode === 'write_off') {
        await writeOff({ warehouse_id: warehouseId, lines: [{ product_id: productId, quantity }] })
      } else {
        if (!toWarehouseId) return
        await transferStock({
          warehouse_id: warehouseId,
          to_warehouse_id: toWarehouseId,
          lines: [{ product_id: productId, quantity }],
        })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выполнить операцию')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      {!fixedWarehouseId && (
        <label className="field">
          {mode === 'transfer' ? 'Склад-отправитель' : 'Склад'}
          <Select
            value={warehouseId != null ? String(warehouseId) : ''}
            onChange={(v) => setWarehouseId(Number(v))}
            options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
          />
        </label>
      )}
      {mode === 'transfer' && (
        <label className="field">
          Склад-получатель
          <Select
            value={toWarehouseId != null ? String(toWarehouseId) : ''}
            onChange={(v) => setToWarehouseId(Number(v))}
            options={otherWarehouses.map((w) => ({ value: String(w.id), label: w.name }))}
          />
        </label>
      )}
      <label className="field">
        Товар
        <Select
          value={productId != null ? String(productId) : ''}
          onChange={(v) => setProductId(Number(v))}
          options={products.map((p) => ({ value: String(p.id), label: p.name }))}
        />
      </label>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Количество
          <input
            type="text"
            inputMode="decimal"
            value={quantity}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setQuantity(normalized)
            }}
            required
          />
        </label>
        {mode === 'receive' && (
          <label className="field" style={{ flex: 1 }}>
            Закупочная цена
            <input
              type="text"
              inputMode="decimal"
              value={cost}
              onChange={(e) => {
                const normalized = normalizeDecimalInput(e.target.value)
                if (normalized !== null) setCost(normalized)
              }}
            />
          </label>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      <Button
        type="submit"
        disabled={saving || !warehouseId || !productId || (mode === 'transfer' && !toWarehouseId)}
      >
        {saving ? 'Проведение…' : `Провести: ${MODE_LABELS[mode]}`}
      </Button>
    </form>
  )
}
