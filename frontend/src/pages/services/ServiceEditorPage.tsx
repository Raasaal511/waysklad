import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import {
  IconChevronLeft,
  IconClock,
  IconPhotoUp,
  IconPlus,
  IconTrash,
  IconUser,
  IconX,
} from '@tabler/icons-react'
import {
  createProduct,
  deleteProduct,
  getProduct,
  setProductPhoto,
  updateProduct,
  type Product,
} from '../../entities/product/api'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { formatDuration, SERVICE_UNIT_LABELS, SERVICE_UNITS } from '../../shared/lib/service'
import { Button } from '../../shared/ui/Button'
import { Chip } from '../../shared/ui/Chip'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Select } from '../../shared/ui/Select'
import { ServicePhoto } from '../../shared/ui/ServicePhoto'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ServiceEditor.module.css'

// самые частые длительности — одним нажатием; остальное вводится минутами
const DURATION_PRESETS = [15, 30, 45, 60, 90, 120]

interface AddonRow {
  key: string
  id: number | null
  name: string
  price: string
}

let rowSeq = 0
const nextKey = () => `row-${++rowSeq}`

/** «1 500,50» → «1500.50»; пустая строка остаётся пустой. */
function normalizePrice(value: string) {
  return value.replace(/\s/g, '').replace(',', '.')
}

function isPrice(value: string) {
  return /^\d+(\.\d{1,2})?$/.test(normalizePrice(value))
}

export function ServiceEditorPage() {
  const { id } = useParams<{ id: string }>()
  const isNew = id === undefined
  const serviceId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'
  const { employees, ensureEmployees, refresh } = useCatalog()

  const [original, setOriginal] = useState<Product | null>(null)
  const [loading, setLoading] = useState(!isNew)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [unitCode, setUnitCode] = useState('service')
  const [duration, setDuration] = useState(0)
  const [customDuration, setCustomDuration] = useState(false)
  const [performerId, setPerformerId] = useState<number | null>(null)
  const [addons, setAddons] = useState<AddonRow[]>([])
  const [description, setDescription] = useState('')
  const [warranty, setWarranty] = useState('')
  const [onStorefront, setOnStorefront] = useState(false)
  const [photo, setPhoto] = useState('')
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState('')

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    ensureEmployees().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (isNew) return
    if (!Number.isFinite(serviceId) || serviceId <= 0) {
      setLoadError('Услуга не найдена')
      setLoading(false)
      return
    }
    let cancelled = false
    getProduct(serviceId)
      .then((s) => {
        if (cancelled) return
        setOriginal(s)
        setName(s.name)
        setPrice(String(Number(s.retail_price)))
        setUnitCode(s.unit_code)
        setDuration(s.duration_minutes)
        setCustomDuration(s.duration_minutes > 0 && !DURATION_PRESETS.includes(s.duration_minutes))
        setPerformerId(s.performer_id)
        setAddons(
          s.variants
            .filter((v) => v.addon)
            .map((v) => ({
              key: nextKey(),
              id: v.id,
              name: v.name,
              price: v.price != null ? String(Number(v.price)) : '',
            })),
        )
        setDescription(s.description)
        setWarranty(s.warranty_text)
        setOnStorefront(s.show_on_storefront)
        setPhoto(s.photo)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : 'Не удалось загрузить услугу')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isNew, serviceId])

  // превью выбранного файла живёт, пока файл выбран
  useEffect(() => {
    if (!photoFile) {
      setPhotoPreview('')
      return
    }
    const url = URL.createObjectURL(photoFile)
    setPhotoPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [photoFile])

  const shownPhoto = photoPreview || photo
  const validAddons = addons.filter((a) => a.name.trim() && isPrice(a.price))
  const basePrice = isPrice(price) ? Number(normalizePrice(price)) : 0
  const maxTotal = basePrice + validAddons.reduce((sum, a) => sum + Number(normalizePrice(a.price)), 0)

  const performerOptions = useMemo(
    () => [
      { value: '', label: 'Не закреплена' },
      ...employees.filter((e) => e.is_active).map((e) => ({ value: String(e.id), label: e.name })),
    ],
    [employees],
  )
  const performerName = employees.find((e) => e.id === performerId)?.name ?? ''

  if (!canManage) return <Navigate to="/services" replace />

  function updateAddon(key: string, patch: Partial<AddonRow>) {
    setAddons((prev) => prev.map((a) => (a.key === key ? { ...a, ...patch } : a)))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!name.trim()) return setError('Назовите услугу')
    if (!isPrice(price)) return setError('Укажите цену — число, например 500')
    const broken = addons.find((a) => (a.name.trim() || a.price) && !(a.name.trim() && isPrice(a.price)))
    if (broken) return setError('У каждого допа нужны название и цена')

    const payload = {
      name: name.trim(),
      unit_code: unitCode,
      retail_price: normalizePrice(price),
      description,
      warranty_text: warranty,
      show_on_storefront: onStorefront,
      duration_minutes: duration,
      performer_id: performerId,
      variants: validAddons.map((a) => ({
        id: a.id,
        size: '',
        color: '',
        name: a.name.trim(),
        price: normalizePrice(a.price),
        addon: true,
      })),
    }

    setSaving(true)
    try {
      let saved: Product
      if (isNew || !original) {
        saved = await createProduct({ ...payload, kind: 'service' })
      } else {
        // PUT заменяет позицию целиком — поля, которых нет в этой форме,
        // переносим как были, иначе они обнулятся
        saved = await updateProduct(original.id, {
          ...payload,
          sku: original.sku,
          barcode: original.barcode,
          category_id: original.category_id,
          storefront_min_qty: original.storefront_min_qty,
          storefront_step_qty: original.storefront_step_qty,
          photo,
        })
      }
      if (photoFile) await setProductPhoto(saved.id, photoFile)
      refresh(['products']).catch(() => {})
      navigate('/services')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить услугу')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!original) return
    try {
      await deleteProduct(original.id)
      refresh(['products']).catch(() => {})
      navigate('/services')
    } catch (err) {
      setConfirmDelete(false)
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить услугу')
    }
  }

  if (loading) return <p className={layoutStyles.textMuted}>Загрузка…</p>
  if (loadError) {
    return (
      <div className={layoutStyles.stack}>
        <p className={layoutStyles.error}>{loadError}</p>
        <Link to="/services">← К услугам</Link>
      </div>
    )
  }

  return (
    <form className={styles.page} onSubmit={handleSubmit} noValidate>
      <Link to="/services" className={styles.back}>
        <IconChevronLeft size={18} stroke={1.8} /> Услуги
      </Link>

      <div className={styles.layout}>
        {/* --- фото --- */}
        <div className={styles.areaPhoto}>
          <div className={styles.photoBox}>
            <ServicePhoto src={shownPhoto} name={name || 'У'} className={styles.photo} />
            <div className={styles.photoActions}>
              <Button type="button" variant="secondary" onClick={() => fileInput.current?.click()}>
                <IconPhotoUp size={16} stroke={1.8} /> {shownPhoto ? 'Заменить' : 'Фото'}
              </Button>
              {shownPhoto && (
                <button
                  type="button"
                  className={styles.linkBtn}
                  onClick={() => {
                    setPhotoFile(null)
                    setPhoto('')
                  }}
                >
                  Убрать
                </button>
              )}
            </div>
            <p className={styles.hint}>Не обязательно: без фото покажем первую букву названия.</p>
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) setPhotoFile(file)
                e.target.value = ''
              }}
            />
          </div>
        </div>

        {/* --- поля --- */}
        <div className={styles.areaInfo}>
          <section className={styles.card}>
            <input
              className={styles.nameInput}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название услуги"
              aria-label="Название услуги"
              autoFocus={isNew}
              maxLength={300}
            />

            <div className={styles.field}>
              <span className={styles.label}>Цена</span>
              <div className={styles.priceRow}>
                <label className={styles.priceInput}>
                  <input
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    inputMode="decimal"
                    placeholder="0"
                    aria-label="Цена"
                  />
                  <span>₽</span>
                </label>
                <div className={styles.chips}>
                  {SERVICE_UNITS.map((code) => (
                    <Chip key={code} active={unitCode === code} onClick={() => setUnitCode(code)}>
                      {SERVICE_UNIT_LABELS[code]}
                    </Chip>
                  ))}
                </div>
              </div>
            </div>

            <div className={styles.field}>
              <span className={styles.label}>Сколько занимает</span>
              <div className={styles.chips}>
                <Chip
                  active={duration === 0 && !customDuration}
                  onClick={() => {
                    setDuration(0)
                    setCustomDuration(false)
                  }}
                >
                  Не важно
                </Chip>
                {DURATION_PRESETS.map((m) => (
                  <Chip
                    key={m}
                    active={!customDuration && duration === m}
                    onClick={() => {
                      setDuration(m)
                      setCustomDuration(false)
                    }}
                  >
                    {formatDuration(m)}
                  </Chip>
                ))}
                <Chip active={customDuration} onClick={() => setCustomDuration(true)}>
                  Другое
                </Chip>
              </div>
              {customDuration && (
                <label className={`${styles.priceInput} ${styles.minutesInput}`}>
                  <input
                    value={duration || ''}
                    onChange={(e) => setDuration(Math.max(0, Number(e.target.value.replace(/\D/g, '')) || 0))}
                    inputMode="numeric"
                    placeholder="0"
                    aria-label="Длительность в минутах"
                    autoFocus
                  />
                  <span>мин</span>
                </label>
              )}
            </div>

            <div className={styles.field}>
              <span className={styles.label}>Кто оказывает</span>
              <Select
                value={performerId != null ? String(performerId) : ''}
                onChange={(v) => setPerformerId(v ? Number(v) : null)}
                options={performerOptions}
              />
            </div>
          </section>

          <section className={styles.card}>
            <div className={styles.cardHead}>
              <h3 className={styles.blockTitle}>Допы</h3>
              <span className={styles.hint}>Клиент отмечает нужные — цена складывается</span>
            </div>
            {addons.length > 0 && (
              <ul className={styles.addons}>
                {addons.map((a) => (
                  <li key={a.key} className={styles.addonRow}>
                    <input
                      className={styles.addonName}
                      value={a.name}
                      onChange={(e) => updateAddon(a.key, { name: e.target.value })}
                      placeholder="Например, балансировка"
                      aria-label="Название допа"
                    />
                    <label className={`${styles.priceInput} ${styles.addonPrice}`}>
                      <span>+</span>
                      <input
                        value={a.price}
                        onChange={(e) => updateAddon(a.key, { price: e.target.value })}
                        inputMode="decimal"
                        placeholder="0"
                        aria-label="Цена допа"
                      />
                      <span>₽</span>
                    </label>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() => setAddons((prev) => prev.filter((x) => x.key !== a.key))}
                      aria-label="Убрать доп"
                    >
                      <IconX size={16} stroke={1.8} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className={styles.addRow}
              onClick={() => setAddons((prev) => [...prev, { key: nextKey(), id: null, name: '', price: '' }])}
            >
              <IconPlus size={16} stroke={1.8} /> Добавить доп
            </button>
          </section>

          <section className={styles.card}>
            <h3 className={styles.blockTitle}>Для клиента</h3>
            <label className={styles.field}>
              <span className={styles.label}>Описание</span>
              <textarea
                className={styles.textarea}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                placeholder="Что входит, как проходит, что взять с собой"
              />
            </label>
            <label className={styles.field}>
              <span className={styles.label}>Гарантия</span>
              <input
                className={styles.input}
                value={warranty}
                onChange={(e) => setWarranty(e.target.value)}
                placeholder="Например, 3 месяца на работу"
                maxLength={5000}
              />
            </label>
          </section>
        </div>

        {/* --- итог: как увидит клиент + сохранение --- */}
        <aside className={styles.areaAside}>
          <section className={`${styles.card} ${styles.summary}`}>
            <div className={styles.summaryHead}>
              <ServicePhoto src={shownPhoto} name={name || 'У'} size={56} />
              <div className={styles.summaryTitle}>
                <strong>{name.trim() || 'Новая услуга'}</strong>
                <div className={styles.summaryMeta}>
                  {duration > 0 && (
                    <span>
                      <IconClock size={14} stroke={1.8} /> {formatDuration(duration)}
                    </span>
                  )}
                  {performerName && (
                    <span>
                      <IconUser size={14} stroke={1.8} /> {performerName}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className={styles.summaryPrice}>
              {validAddons.length > 0 && <span className={styles.muted}>от</span>}
              <strong>{formatMoney(basePrice)} ₽</strong>
              <span className={styles.muted}>{SERVICE_UNIT_LABELS[unitCode]}</span>
            </div>
            {validAddons.length > 0 && (
              <p className={styles.muted}>Со всеми допами — {formatMoney(maxTotal)} ₽</p>
            )}

            <label className={styles.switchRow}>
              <span>
                Показывать на витрине
                <small className={styles.muted}>Клиенты увидят услугу во вкладке «Услуги»</small>
              </span>
              <input
                type="checkbox"
                className={styles.switch}
                checked={onStorefront}
                onChange={(e) => setOnStorefront(e.target.checked)}
              />
            </label>

            {error && <p className={layoutStyles.error}>{error}</p>}

            <Button type="submit" disabled={saving} className={styles.save}>
              {saving ? 'Сохраняем…' : isNew ? 'Добавить услугу' : 'Сохранить'}
            </Button>
            {!isNew && (
              <button type="button" className={styles.delete} onClick={() => setConfirmDelete(true)}>
                <IconTrash size={16} stroke={1.8} /> Удалить услугу
              </button>
            )}
          </section>
        </aside>
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Удалить услугу?"
          message="Услуга исчезнет из списка и с витрины. Прошлые чеки останутся как есть."
          confirmLabel="Удалить"
          danger
          onConfirm={handleDelete}
          onClose={() => setConfirmDelete(false)}
        />
      )}
    </form>
  )
}
