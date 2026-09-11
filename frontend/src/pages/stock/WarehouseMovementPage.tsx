import { useEffect, useState, type CSSProperties } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { changeTaskStatus } from '../../entities/task/api'
import { ApiError } from '../../shared/api/client'
import { useCatalog } from '../../app/CatalogContext'
import { IconChevronLeft } from '@tabler/icons-react'
import { loadReceiveDraft, clearReceiveDraft } from './receiveDraft'
import {
  MODE_LABELS,
  MovementForm,
  type MovementMode,
  type MovementLine,
} from './shared'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from '../products/ProductDetailPage.module.css'

const VALID_MODES: MovementMode[] = ['receive', 'write_off', 'transfer', 'stocktake']

export function WarehouseMovementPage() {
  const { id, mode: modeParam } = useParams<{ id: string; mode: string }>()
  const warehouseId = Number(id)
  const mode = (VALID_MODES.includes(modeParam as MovementMode) ? modeParam : null) as MovementMode | null
  const navigate = useNavigate()

  const {
    products,
    units,
    categories,
    warehouses,
    stock: allStock,
    ensureProducts,
    ensureUnits,
    ensureCategories,
    ensureWarehouses,
    ensureStock,
    refresh: refreshCatalog,
  } = useCatalog()

  const warehouse = warehouses.find((w) => w.id === warehouseId) ?? null
  const [lines, setLines] = useState<MovementLine[] | undefined>(undefined)
  const [pendingTaskId, setPendingTaskId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!mode || !Number.isFinite(warehouseId) || warehouseId <= 0) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setReady(false)
    Promise.all([
      ensureStock(),
      ensureWarehouses(),
      ensureProducts(),
      ensureUnits(),
      ensureCategories(),
    ])
      .then(([, , p]) => {
        if (cancelled) return
        if (mode === 'receive') {
          const draft = loadReceiveDraft()
          if (draft && draft.warehouseId === warehouseId) {
            const seeded: MovementLine[] = draft.lines.flatMap((l) => {
              const product = p.find((x) => x.id === l.productId)
              return product
                ? [{ product, quantity: l.quantity || '1', cost: product.purchase_price ?? '' }]
                : []
            })
            setLines(seeded)
            setPendingTaskId(draft.fromTaskId ?? null)
            clearReceiveDraft()
          }
        }
        setReady(true)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Не удалось загрузить данные')
          setReady(true)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseId, mode])

  if (!mode) {
    return <Navigate to={Number.isFinite(warehouseId) ? `/stock/${warehouseId}` : '/stock'} replace />
  }

  if (!loading && !warehouse) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/stock" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все склады
        </Link>
        <p className={layoutStyles.error}>{error ?? 'Склад не найден'}</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to={`/stock/${warehouseId}`} className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> {warehouse?.name ?? 'Склад'}
      </Link>

      <div
        className={`${layoutStyles.sectionTitle} ${detail.reveal}`}
        style={{ '--reveal-delay': '0ms' } as CSSProperties}
      >
        <h2>
          {MODE_LABELS[mode]}
          {warehouse ? ` · ${warehouse.name}` : ''}
        </h2>
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}

      {loading || !warehouse || !ready ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <div className={detail.reveal} style={{ '--reveal-delay': '60ms' } as CSSProperties}>
          <MovementForm
            mode={mode}
            products={products}
            warehouses={warehouses}
            units={units}
            categories={categories}
            stock={allStock}
            fixedWarehouseId={warehouse.id}
            lines={lines}
            onLinesChange={setLines}
            onDone={() => {
              if (mode === 'receive' && pendingTaskId != null) {
                changeTaskStatus(pendingTaskId, 'done').catch(() => {})
                setPendingTaskId(null)
              }
              refreshCatalog(['stock', 'products']).catch(() => {})
              navigate(`/stock/${warehouseId}`, { replace: true })
            }}
          />
        </div>
      )}
    </div>
  )
}
