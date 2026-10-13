import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconPlus, IconClock, IconUser } from '@tabler/icons-react'
import { listProducts, type Product } from '../../entities/product/api'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { formatDuration, SERVICE_UNIT_LABELS } from '../../shared/lib/service'
import { Button } from '../../shared/ui/Button'
import { EmptyState } from '../../shared/ui/EmptyState'
import { SearchField } from '../../shared/ui/SearchField'
import { ServicePhoto } from '../../shared/ui/ServicePhoto'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ServicesPage.module.css'

export function ServicesPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'
  const navigate = useNavigate()
  const { employees, ensureEmployees } = useCatalog()

  const [services, setServices] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    ensureEmployees().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    listProducts({ kind: 'service', query: debounced, limit: 50 })
      .then(({ items }) => {
        if (!cancelled) setServices(items)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Не удалось загрузить услуги')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [debounced])

  const performerName = useMemo(() => {
    const map = new Map(employees.map((e) => [e.id, e.name]))
    return (id: number | null) => (id != null ? map.get(id) ?? '' : '')
  }, [employees])

  const isEmptyShop = !loading && !error && services.length === 0 && !debounced

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Услуги</h2>
        {canManage && (
          <Button onClick={() => navigate('/services/new')}>
            <IconPlus size={16} stroke={1.8} /> Услуга
          </Button>
        )}
      </div>

      {isEmptyShop ? (
        <EmptyState
          title="Пока нет услуг"
          description="Шиномонтаж, доставка, установка — всё, что вы делаете руками. Услуга продаётся в том же чеке, что товар, и не трогает склад."
          actionLabel={canManage ? 'Добавить услугу' : undefined}
          onAction={canManage ? () => navigate('/services/new') : undefined}
        />
      ) : (
        <>
          <SearchField value={query} onChange={setQuery} placeholder="Поиск услуги" />

          {error && <p className={layoutStyles.error}>{error}</p>}
          {loading && services.length === 0 ? (
            <p className={layoutStyles.textMuted}>Загрузка…</p>
          ) : services.length === 0 ? (
            <p className={layoutStyles.textMuted}>Ничего не нашлось</p>
          ) : (
            <div className={styles.grid}>
              {services.map((s) => {
                const addons = s.variants.filter((v) => v.addon)
                const duration = formatDuration(s.duration_minutes)
                const performer = performerName(s.performer_id)
                const body = (
                  <>
                    <ServicePhoto src={s.photo} name={s.name} className={styles.cardPhoto} />
                    <div className={styles.cardBody}>
                      <strong className={styles.cardName}>{s.name}</strong>
                      {(duration || performer) && (
                        <div className={styles.cardMeta}>
                          {duration && (
                            <span>
                              <IconClock size={14} stroke={1.8} /> {duration}
                            </span>
                          )}
                          {performer && (
                            <span>
                              <IconUser size={14} stroke={1.8} /> {performer}
                            </span>
                          )}
                        </div>
                      )}
                      <div className={styles.cardPrice}>
                        {addons.length > 0 && <span className={styles.cardFrom}>от</span>}
                        {formatMoney(s.retail_price)} ₽
                        <span className={styles.cardUnit}>
                          {SERVICE_UNIT_LABELS[s.unit_code] ?? ''}
                        </span>
                      </div>
                      {(addons.length > 0 || s.show_on_storefront) && (
                        <div className={styles.cardTags}>
                          {addons.length > 0 && (
                            <span className={styles.tag}>
                              {addons.length} {pluralAddons(addons.length)}
                            </span>
                          )}
                          {s.show_on_storefront && (
                            <span className={`${styles.tag} ${styles.tagAccent}`}>На витрине</span>
                          )}
                        </div>
                      )}
                    </div>
                  </>
                )
                // продавец видит услуги, но правит их владелец или менеджер
                return canManage ? (
                  <Link key={s.id} to={`/services/${s.id}`} className={styles.card}>
                    {body}
                  </Link>
                ) : (
                  <div key={s.id} className={styles.card}>
                    {body}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function pluralAddons(n: number) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'доп'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'допа'
  return 'допов'
}
