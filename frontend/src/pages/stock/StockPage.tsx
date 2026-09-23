import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus, IconBuildingWarehouse, IconChevronRight, IconHistory } from '@tabler/icons-react'
import { IconButton } from '../../shared/ui/IconButton'
import { Button } from '../../shared/ui/Button'
import { EmptyState } from '../../shared/ui/EmptyState'
import { isLowStock } from '../../shared/lib/format'
import { NewWarehouseForm } from './shared'
import { useCatalog } from '../../app/CatalogContext'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function StockPage() {
  const { stock, warehouses, products, ensureStock, ensureWarehouses, ensureProducts, refresh: refreshCatalog } =
    useCatalog()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showWarehouseForm, setShowWarehouseForm] = useState(false)

  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      await Promise.all([ensureStock(), ensureWarehouses(), ensureProducts()])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить остатки')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const minStockById = new Map(products.map((p) => [p.id, p.min_stock]))
  const itemCount = (warehouseId: number) => stock.filter((s) => s.warehouse_id === warehouseId).length
  const lowStockCount = (warehouseId: number) =>
    stock.filter(
      (s) => s.warehouse_id === warehouseId && isLowStock(s.quantity, minStockById.get(s.product_id) ?? '0'),
    ).length

  const totalPositions = stock.length
  const totalLowStock = stock.filter((s) => isLowStock(s.quantity, minStockById.get(s.product_id) ?? '0')).length

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Склады</h2>
        <div className={layoutStyles.pageTitleActions}>
          <div className={layoutStyles.pageTitleActionsDesktop}>
            <Link to="/stock/history">
              <IconButton variant="accent" tooltip="История движения" style={{ width: 40, height: 40 }}>
                <IconHistory size={19} stroke={1.8} />
              </IconButton>
            </Link>
            <Button onClick={() => setShowWarehouseForm(true)}>
              <IconPlus size={16} stroke={1.8} /> Склад
            </Button>
          </div>
          <div className={layoutStyles.pageTitleActionsMobile}>
            <Link to="/stock/history" aria-label="История движения">
              <IconButton variant="muted" size="lg">
                <IconHistory size={20} stroke={1.8} />
              </IconButton>
            </Link>
            <IconButton
              variant="accent"
              size="lg"
              aria-label="Добавить склад"
              onClick={() => setShowWarehouseForm(true)}
            >
              <IconPlus size={20} stroke={2} />
            </IconButton>
          </div>
        </div>
      </div>

      {showWarehouseForm && (
        <Modal title="Новый склад" onClose={() => setShowWarehouseForm(false)}>
          <NewWarehouseForm
            onCreated={() => {
              setShowWarehouseForm(false)
              refreshCatalog(['warehouses']).catch(() => {})
            }}
          />
        </Modal>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}

      {!loading && warehouses.length > 1 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull].join(' ')}>
          <div className={layoutStyles.gridStats}>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Складов</span>
              <span className={layoutStyles.statValue}>{warehouses.length}</span>
            </div>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Позиций на остатке</span>
              <span className={layoutStyles.statValue}>{totalPositions}</span>
            </div>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Заканчивается</span>
              <span className={layoutStyles.statValue}>{totalLowStock}</span>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : warehouses.length === 0 ? (
        <EmptyState
          illustration="empty-stock"
          title="Складов пока нет"
          description="Создайте склад — туда будете принимать товар и списывать продажи."
          actionLabel="Добавить склад"
          onAction={() => setShowWarehouseForm(true)}
        />
      ) : (
        <div className={layoutStyles.warehouseTiles}>
          {warehouses.map((w, i) => {
            const low = lowStockCount(w.id)
            return (
              <Link
                key={w.id}
                to={`/stock/${w.id}`}
                className={`${layoutStyles.warehouseTile} sale-history-row-in`}
                style={{ '--row-delay': `${Math.min(i, 12) * 40}ms` } as CSSProperties}
              >
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
                  <div className={layoutStyles.stat}>
                    <span className={layoutStyles.statLabel}>Заканчивается</span>
                    <span
                      className={[layoutStyles.statValue, low > 0 && layoutStyles.statValueWarning]
                        .filter(Boolean)
                        .join(' ')}
                    >
                      {low}
                    </span>
                  </div>
                  <div className={layoutStyles.stat}>
                    <span className={layoutStyles.statLabel}>Ответственных</span>
                    <span className={layoutStyles.statValue}>{w.assigned_user_ids.length}</span>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
