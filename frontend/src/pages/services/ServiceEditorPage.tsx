import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import {
  IconCheck,
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
import { Chip } from '../../shared/ui/Chip'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Select } from '../../shared/ui/Select'
import { ServicePhoto } from '../../shared/ui/ServicePhoto'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ServiceEditor.module.css'

// самые частые длительности — одним нажатием; остальное вводится минутами
const DURATION_PRESETS = [15, 30, 45, 60, 90, 120]

// пустая форма новой услуги: одно нажатие вместо набора названия,
// заодно подставляется то, что у такой услуги почти всегда одинаково
const NAME_TEMPLATES: { name: string; unit?: string; duration?: number }[] = [
  { name: 'Доставка', unit: 'visit' },
  { name: 'Установка', duration: 60 },
  { name: 'Ремонт' },
  { name: 'Консультация', duration: 30 },
  { name: 'Выезд мастера', unit: 'visit' },
]

// частые допы почти у любой услуги
const ADDON_SUGGESTIONS = ['Срочно', 'Выезд к клиенту', 'Материалы']

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

/** Число плавно «докручивается» до нового значения — итог не прыгает. */
function useTween(value: number, ms = 280) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    const start = performance.now()
    const begin = from.current
    let frame = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - (1 - t) ** 3
      const current = begin + (value - begin) * eased
      from.current = current
      setShown(current)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, ms])
  return Math.round(shown)
}

const EMPTY = {
  name: '',
  price: '',
  unitCode: 'service',
  duration: 0,
  performerId: null as number | null,
  addons: [] as AddonRow[],
  description: '',
  warranty: '',
  onStorefront: false,
  photo: '',
}
type FormState = typeof EMPTY

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

  const [form, setForm] = useState<FormState>(EMPTY)
  const [initial, setInitial] = useState<FormState>(EMPTY)
  const [customDuration, setCustomDuration] = useState(false)
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState('')
  const [dragOver, setDragOver] = useState(false)
  // какие допы «отметил клиент» в превью — только для наглядности итога
  const [previewPicked, setPreviewPicked] = useState<Set<string>>(new Set())

  const [saving, setSaving] = useState<null | 'stay' | 'leave'>(null)
  const [saved, setSaved] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const nameInput = useRef<HTMLInputElement>(null)
  const priceInput = useRef<HTMLInputElement>(null)
  const focusPrice = useRef(false)
  const formRef = useRef<HTMLFormElement>(null)
  const addonPriceRefs = useRef(new Map<string, HTMLInputElement>())
  // куда поставить курсор после следующего рендера списка допов
  const focusAddon = useRef<{ key: string; field: 'name' | 'price' } | null>(null)

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

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
        const loaded: FormState = {
          name: s.name,
          price: String(Number(s.retail_price)),
          unitCode: s.unit_code,
          duration: s.duration_minutes,
          performerId: s.performer_id,
          addons: s.variants
            .filter((v) => v.addon)
            .map((v) => ({
              key: nextKey(),
              id: v.id,
              name: v.name,
              price: v.price != null ? String(Number(v.price)) : '',
            })),
          description: s.description,
          warranty: s.warranty_text,
          onStorefront: s.show_on_storefront,
          photo: s.photo,
        }
        setOriginal(s)
        setForm(loaded)
        setInitial(loaded)
        setCustomDuration(s.duration_minutes > 0 && !DURATION_PRESETS.includes(s.duration_minutes))
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

  const dirty = photoFile !== null || JSON.stringify(form) !== JSON.stringify(initial)

  // закрыть вкладку с несохранённой услугой — браузер переспросит
  useEffect(() => {
    if (!dirty || saved) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty, saved])

  // фото из буфера: скриншот или картинка из мессенджера — Ctrl+V прямо на странице
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const file = [...(e.clipboardData?.files ?? [])].find((f) => f.type.startsWith('image/'))
      if (file) {
        e.preventDefault()
        setPhotoFile(file)
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [])

  // Ctrl/⌘+Enter — сохранить из любого поля
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        formRef.current?.requestSubmit()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // новый доп: курсор сразу в его название, а у подсказки с готовым
  // названием — в цену. Эффект, а не rAF: успевает до следующей клавиши
  useEffect(() => {
    const target = focusAddon.current
    if (!target) return
    focusAddon.current = null
    if (target.field === 'price') addonPriceRefs.current.get(target.key)?.focus()
    else document.querySelector<HTMLInputElement>(`[data-addon-name="${target.key}"]`)?.focus()
  }, [form.addons])

  // после шаблона названия — курсор в цену (эффект, чтобы успеть до клавиш)
  useEffect(() => {
    if (!focusPrice.current) return
    focusPrice.current = false
    priceInput.current?.focus()
  }, [form.name])

  const shownPhoto = photoPreview || form.photo
  const validAddons = form.addons.filter((a) => a.name.trim() && isPrice(a.price))
  const basePrice = isPrice(form.price) ? Number(normalizePrice(form.price)) : 0
  const pickedSum = validAddons
    .filter((a) => previewPicked.has(a.key))
    .reduce((sum, a) => sum + Number(normalizePrice(a.price)), 0)
  const total = useTween(basePrice + pickedSum)

  const performerOptions = useMemo(
    () => [
      { value: '', label: 'Не закреплена' },
      ...employees.filter((e) => e.is_active).map((e) => ({ value: String(e.id), label: e.name })),
    ],
    [employees],
  )
  const performerName = employees.find((e) => e.id === form.performerId)?.name ?? ''

  const addAddon = useCallback((name = '') => {
    const key = nextKey()
    focusAddon.current = { key, field: name ? 'price' : 'name' }
    setForm((prev) => ({ ...prev, addons: [...prev.addons, { key, id: null, name, price: '' }] }))
  }, [])

  if (!canManage) return <Navigate to="/services" replace />

  function updateAddon(key: string, patch: Partial<AddonRow>) {
    setForm((prev) => ({
      ...prev,
      addons: prev.addons.map((a) => (a.key === key ? { ...a, ...patch } : a)),
    }))
  }

  function acceptPhoto(file: File | undefined) {
    if (file && file.type.startsWith('image/')) setPhotoFile(file)
  }

  async function save(mode: 'stay' | 'leave') {
    setError(null)
    if (!form.name.trim()) {
      nameInput.current?.focus()
      return setError('Назовите услугу')
    }
    if (!isPrice(form.price)) return setError('Укажите цену — число, например 500')
    const broken = form.addons.find(
      (a) => (a.name.trim() || a.price) && !(a.name.trim() && isPrice(a.price)),
    )
    if (broken) return setError('У каждого допа нужны название и цена')

    const payload = {
      name: form.name.trim(),
      unit_code: form.unitCode,
      retail_price: normalizePrice(form.price),
      description: form.description,
      warranty_text: form.warranty,
      show_on_storefront: form.onStorefront,
      duration_minutes: form.duration,
      performer_id: form.performerId,
      variants: validAddons.map((a) => ({
        id: a.id,
        size: '',
        color: '',
        name: a.name.trim(),
        price: normalizePrice(a.price),
        addon: true,
      })),
    }

    setSaving(mode)
    try {
      let result: Product
      if (isNew || !original) {
        result = await createProduct({ ...payload, kind: 'service' })
      } else {
        // PUT заменяет позицию целиком — поля, которых нет в этой форме,
        // переносим как были, иначе они обнулятся
        result = await updateProduct(original.id, {
          ...payload,
          sku: original.sku,
          barcode: original.barcode,
          category_id: original.category_id,
          storefront_min_qty: original.storefront_min_qty,
          storefront_step_qty: original.storefront_step_qty,
          photo: form.photo,
        })
      }
      if (photoFile) await setProductPhoto(result.id, photoFile)
      refresh(['products']).catch(() => {})

      if (mode === 'stay') {
        // «и добавить ещё»: каталог заполняют подряд — единица и исполнитель
        // обычно те же, остальное с чистого листа
        const next = { ...EMPTY, unitCode: form.unitCode, performerId: form.performerId }
        setForm(next)
        setInitial(next)
        setPhotoFile(null)
        setPreviewPicked(new Set())
        setCustomDuration(false)
        setFlash(`«${result.name}» добавлена`)
        setTimeout(() => setFlash(null), 2600)
        nameInput.current?.focus()
      } else {
        setSaved(true)
        setTimeout(() => navigate('/services'), 450)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить услугу')
    } finally {
      setSaving(null)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    save('leave')
  }

  async function handleDelete() {
    if (!original) return
    try {
      await deleteProduct(original.id)
      refresh(['products']).catch(() => {})
      setSaved(true)
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

  const submitLabel = saved ? 'Сохранено' : saving === 'leave' ? 'Сохраняем…' : isNew ? 'Добавить услугу' : 'Сохранить'

  return (
    <form ref={formRef} className={styles.page} onSubmit={handleSubmit} noValidate>
      <header className={styles.top}>
        <Link to="/services" className={styles.back}>
          <IconChevronLeft size={18} stroke={1.8} /> Услуги
        </Link>
        <h2 className={styles.title}>{isNew ? 'Новая услуга' : form.name || 'Услуга'}</h2>
        {flash && (
          <span className={styles.flash} role="status">
            <IconCheck size={16} stroke={2.2} /> {flash}
          </span>
        )}
      </header>

      <div className={styles.layout}>
        <div className={styles.main}>
          {/* --- основное --- */}
          <section className={styles.card}>
            <div className={styles.identity}>
              <button
                type="button"
                className={[styles.drop, dragOver && styles.dropActive].filter(Boolean).join(' ')}
                onClick={() => fileInput.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragOver(true)
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  acceptPhoto(e.dataTransfer.files[0])
                }}
                aria-label={shownPhoto ? 'Заменить фото' : 'Добавить фото'}
                title="Нажмите, перетащите или вставьте фото (Ctrl+V)"
              >
                <ServicePhoto src={shownPhoto} name={form.name || '+'} className={styles.dropPhoto} />
                <span className={styles.dropOverlay}>
                  <IconPhotoUp size={22} stroke={1.8} />
                  {shownPhoto ? 'Заменить' : 'Фото'}
                </span>
              </button>
              {shownPhoto && (
                <button
                  type="button"
                  className={styles.dropRemove}
                  onClick={() => {
                    setPhotoFile(null)
                    set('photo', '')
                  }}
                  aria-label="Убрать фото"
                >
                  <IconX size={14} stroke={2.2} />
                </button>
              )}
              <input
                ref={fileInput}
                type="file"
                accept="image/*"
                hidden
                onChange={(e) => {
                  acceptPhoto(e.target.files?.[0])
                  e.target.value = ''
                }}
              />

              <div className={styles.identityText}>
                <input
                  ref={nameInput}
                  className={styles.nameInput}
                  value={form.name}
                  onChange={(e) => set('name', e.target.value)}
                  placeholder="Как называется услуга?"
                  aria-label="Название услуги"
                  autoFocus={isNew}
                  maxLength={300}
                />
                {isNew && !form.name && (
                  <div className={styles.templates}>
                    {NAME_TEMPLATES.map((t) => (
                      <button
                        key={t.name}
                        type="button"
                        className={styles.template}
                        onClick={() => {
                          setForm((prev) => ({
                            ...prev,
                            name: t.name,
                            unitCode: t.unit ?? prev.unitCode,
                            duration: t.duration ?? prev.duration,
                          }))
                          setCustomDuration(false)
                          focusPrice.current = true
                        }}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                )}
                {!shownPhoto && (form.name || !isNew) && (
                  <p className={styles.hint}>Фото не обязательно — без него клиент увидит букву.</p>
                )}
              </div>
            </div>

            <div className={styles.field}>
              <span className={styles.label}>Цена</span>
              <div className={styles.priceRow}>
                <label className={styles.priceInput}>
                  <input
                    ref={priceInput}
                    value={form.price}
                    onChange={(e) => set('price', e.target.value)}
                    inputMode="decimal"
                    placeholder="0"
                    aria-label="Цена"
                  />
                  <span>₽</span>
                </label>
                <div className={styles.segmented} role="radiogroup" aria-label="За что цена">
                  {SERVICE_UNITS.map((code) => (
                    <button
                      key={code}
                      type="button"
                      role="radio"
                      aria-checked={form.unitCode === code}
                      className={form.unitCode === code ? styles.segmentActive : styles.segment}
                      onClick={() => set('unitCode', code)}
                    >
                      {SERVICE_UNIT_LABELS[code]}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className={styles.field}>
              <span className={styles.label}>
                <IconClock size={14} stroke={1.8} /> Сколько занимает
              </span>
              <div className={styles.chips}>
                <Chip
                  active={form.duration === 0 && !customDuration}
                  onClick={() => {
                    set('duration', 0)
                    setCustomDuration(false)
                  }}
                >
                  Не важно
                </Chip>
                {DURATION_PRESETS.map((m) => (
                  <Chip
                    key={m}
                    active={!customDuration && form.duration === m}
                    onClick={() => {
                      set('duration', m)
                      setCustomDuration(false)
                    }}
                  >
                    {formatDuration(m)}
                  </Chip>
                ))}
                {customDuration ? (
                  <label className={styles.minutes}>
                    <input
                      value={form.duration || ''}
                      onChange={(e) =>
                        set('duration', Math.max(0, Number(e.target.value.replace(/\D/g, '')) || 0))
                      }
                      inputMode="numeric"
                      placeholder="0"
                      aria-label="Длительность в минутах"
                      autoFocus
                    />
                    мин
                  </label>
                ) : (
                  <Chip active={false} onClick={() => setCustomDuration(true)}>
                    Своё время
                  </Chip>
                )}
              </div>
            </div>

            <div className={styles.field}>
              <span className={styles.label}>
                <IconUser size={14} stroke={1.8} /> Кто оказывает
              </span>
              <Select
                value={form.performerId != null ? String(form.performerId) : ''}
                onChange={(v) => set('performerId', v ? Number(v) : null)}
                options={performerOptions}
              />
            </div>
          </section>

          {/* --- допы --- */}
          <section className={styles.card}>
            <div className={styles.cardHead}>
              <h3 className={styles.blockTitle}>Допы</h3>
              <span className={styles.hint}>Клиент отмечает нужные — цена складывается</span>
            </div>
            {form.addons.length > 0 && (
              <ul className={styles.addons}>
                {form.addons.map((a) => (
                  <li key={a.key} className={styles.addonRow}>
                    <input
                      data-addon-name={a.key}
                      className={styles.addonName}
                      value={a.name}
                      onChange={(e) => updateAddon(a.key, { name: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          addonPriceRefs.current.get(a.key)?.focus()
                        }
                      }}
                      placeholder="Название допа"
                      aria-label="Название допа"
                    />
                    <label className={`${styles.priceInput} ${styles.addonPrice}`}>
                      <span>+</span>
                      <input
                        ref={(el) => {
                          if (el) addonPriceRefs.current.set(a.key, el)
                          else addonPriceRefs.current.delete(a.key)
                        }}
                        value={a.price}
                        onChange={(e) => updateAddon(a.key, { price: e.target.value })}
                        onKeyDown={(e) => {
                          // Enter в цене — сразу следующий доп, без мыши
                          if (e.key === 'Enter') {
                            e.preventDefault()
                            addAddon()
                          }
                        }}
                        inputMode="decimal"
                        placeholder="0"
                        aria-label="Цена допа"
                      />
                      <span>₽</span>
                    </label>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() =>
                        setForm((prev) => ({ ...prev, addons: prev.addons.filter((x) => x.key !== a.key) }))
                      }
                      aria-label="Убрать доп"
                    >
                      <IconX size={16} stroke={1.8} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className={styles.addRowWrap}>
              <button type="button" className={styles.addRow} onClick={() => addAddon()}>
                <IconPlus size={16} stroke={1.8} /> Добавить доп
              </button>
              {form.addons.length === 0 &&
                ADDON_SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className={styles.template} onClick={() => addAddon(s)}>
                    + {s}
                  </button>
                ))}
            </div>
          </section>

          {/* --- для клиента --- */}
          <section className={styles.card}>
            <h3 className={styles.blockTitle}>Для клиента</h3>
            <label className={styles.field}>
              <span className={styles.label}>Описание</span>
              <textarea
                className={styles.textarea}
                value={form.description}
                onChange={(e) => set('description', e.target.value)}
                rows={4}
                placeholder="Что входит, как проходит, что взять с собой"
              />
            </label>
            <label className={styles.field}>
              <span className={styles.label}>Гарантия</span>
              <input
                className={styles.input}
                value={form.warranty}
                onChange={(e) => set('warranty', e.target.value)}
                placeholder="Например, 3 месяца на работу"
                maxLength={5000}
              />
            </label>
          </section>
        </div>

        {/* --- как увидит клиент + сохранение --- */}
        <aside className={styles.aside}>
          <span className={styles.asideLabel}>Так увидит клиент</span>
          <div className={styles.preview}>
            <ServicePhoto src={shownPhoto} name={form.name || 'У'} className={styles.previewPhoto} />
            <div className={styles.previewBody}>
              <strong className={styles.previewName}>{form.name.trim() || 'Название услуги'}</strong>
              {(form.duration > 0 || performerName) && (
                <div className={styles.previewMeta}>
                  {form.duration > 0 && (
                    <span>
                      <IconClock size={14} stroke={1.8} /> {formatDuration(form.duration)}
                    </span>
                  )}
                  {performerName && (
                    <span>
                      <IconUser size={14} stroke={1.8} /> {performerName}
                    </span>
                  )}
                </div>
              )}

              {validAddons.length > 0 && (
                <ul className={styles.previewAddons}>
                  {validAddons.map((a) => {
                    const picked = previewPicked.has(a.key)
                    return (
                      <li key={a.key}>
                        <button
                          type="button"
                          className={picked ? styles.pickActive : styles.pick}
                          aria-pressed={picked}
                          onClick={() =>
                            setPreviewPicked((prev) => {
                              const next = new Set(prev)
                              if (picked) next.delete(a.key)
                              else next.add(a.key)
                              return next
                            })
                          }
                        >
                          <span className={styles.pickBox}>
                            <IconCheck size={12} stroke={3} />
                          </span>
                          <span className={styles.pickName}>{a.name}</span>
                          <span className={styles.pickPrice}>+{formatMoney(a.price)} ₽</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}

              <div className={styles.previewTotal}>
                <span className={styles.muted}>{pickedSum > 0 ? 'Итого' : validAddons.length ? 'от' : 'Цена'}</span>
                <strong>{formatMoney(total)} ₽</strong>
                <span className={styles.muted}>{SERVICE_UNIT_LABELS[form.unitCode]}</span>
              </div>
            </div>
          </div>

          <label className={styles.switchRow}>
            <span>
              На витрине
              <small className={styles.muted}>
                {form.onStorefront ? 'Клиенты видят и могут заказать' : 'Пока видно только в кабинете'}
              </small>
            </span>
            <input
              type="checkbox"
              className={styles.switch}
              checked={form.onStorefront}
              onChange={(e) => set('onStorefront', e.target.checked)}
            />
          </label>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <div className={styles.actions}>
            <button
              type="submit"
              className={[styles.save, saved && styles.saveDone].filter(Boolean).join(' ')}
              disabled={saving !== null || saved}
            >
              {saved && <IconCheck size={18} stroke={2.4} />}
              {submitLabel}
            </button>
            {isNew && (
              <button
                type="button"
                className={styles.saveMore}
                disabled={saving !== null || saved}
                onClick={() => save('stay')}
              >
                {saving === 'stay' ? 'Сохраняем…' : 'Сохранить и добавить ещё'}
              </button>
            )}
            <span className={styles.kbdHint}>Ctrl + Enter — сохранить</span>
          </div>

          {!isNew && (
            <button type="button" className={styles.delete} onClick={() => setConfirmDelete(true)}>
              <IconTrash size={16} stroke={1.8} /> Удалить услугу
            </button>
          )}
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
