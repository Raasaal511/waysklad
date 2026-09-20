import { useEffect, useRef, useState, type CSSProperties } from 'react'
import {
  IconFileSpreadsheet,
  IconCloudUpload,
  IconX,
  IconCircleCheck,
  IconAlertTriangle,
  IconChevronDown,
  IconListDetails,
} from '@tabler/icons-react'
import { DropdownMenu } from '../../shared/ui/DropdownMenu'
import {
  previewImport,
  applyImport,
  type ApplyImportResult,
  type ApplyImportRow,
  type Category,
  type DuplicateCandidate,
  type ExistingProductSnapshot,
  type ImportAction,
  type ImportMatchStatus,
  type PreviewRow,
  type Unit,
} from '../../entities/product/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { normalizeDecimalInput, plural } from '../../shared/lib/format'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ImportProductsModal.module.css'

function categoryOptions(categories: Category[]): { value: string; label: string }[] {
  const result: { value: string; label: string }[] = []
  const visited = new Set<number>()

  function addChildren(parentId: number | null, depth: number) {
    for (const category of categories) {
      if (category.parent_id !== parentId || visited.has(category.id)) continue
      visited.add(category.id)
      result.push({ value: String(category.id), label: `${'— '.repeat(depth)}${category.name}` })
      addChildren(category.id, depth + 1)
    }
  }

  addChildren(null, 0)
  return result
}

type WizardStep = 'upload' | 'preview' | 'result'

interface EditableRow {
  clientRowId: string
  sourceRow: number
  included: boolean
  action: ImportAction
  actionTouched: boolean
  status: ImportMatchStatus
  candidates: DuplicateCandidate[]
  selectedCandidateProductId: number | null
  parseError: string | null
  name: string
  sku: string
  barcode: string
  unitCode: string
  purchasePrice: string
  retailPrice: string
  minStock: string
  categoryId: number | null
}

function toEditableRow(r: PreviewRow): EditableRow {
  const bestCandidate = r.candidates[0] ?? null
  const defaultAction: ImportAction = r.parse_error
    ? 'skip'
    : r.status === 'no_match'
      ? 'create'
      : r.status === 'match'
        ? 'update'
        : 'create' // ambiguous_match — не перезаписываем не тот товар молча
  return {
    clientRowId: `row-${r.row}`,
    sourceRow: r.row,
    included: r.parse_error === null,
    action: defaultAction,
    actionTouched: false,
    status: r.status,
    candidates: r.candidates,
    selectedCandidateProductId: r.status === 'match' ? (bestCandidate?.product.id ?? null) : null,
    parseError: r.parse_error,
    name: r.name,
    sku: r.sku,
    barcode: r.barcode ?? '',
    unitCode: r.unit_code,
    purchasePrice: r.purchase_price ?? '',
    retailPrice: r.retail_price ?? '',
    minStock: r.min_stock,
    // приоритет — категория совпавшего существующего товара (не перезатираем её
    // молча), иначе — категория, распознанная из колонки файла по названию
    categoryId: bestCandidate?.product.category_id ?? r.category_id ?? null,
  }
}

function buildApplyRows(rows: EditableRow[]): ApplyImportRow[] {
  return rows
    .filter((r) => r.included)
    .map((r) => ({
      client_row_id: r.clientRowId,
      action: r.action,
      name: r.name.trim(),
      sku: r.sku.trim(),
      barcode: r.barcode.trim() || null,
      unit_code: r.unitCode,
      purchase_price: r.purchasePrice || '0',
      retail_price: r.retailPrice || '0',
      category_id: r.categoryId,
      min_stock: r.minStock || '0',
      existing_product_id: r.action === 'update' ? r.selectedCandidateProductId : null,
    }))
}

export function ImportProductsModal({
  format,
  onClose,
  onDone,
}: {
  format: 'xlsx' | 'csv'
  onClose: () => void
  onDone: () => void
}) {
  const [step, setStep] = useState<WizardStep>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [rows, setRows] = useState<EditableRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ApplyImportResult | null>(null)
  const { categories, units, ensureCategories, ensureUnits } = useCatalog()

  useEffect(() => {
    ensureCategories()
    ensureUnits()
  }, [ensureCategories, ensureUnits])

  async function handlePreview() {
    if (!file) return
    setError(null)
    setLoading(true)
    try {
      const res = await previewImport(file)
      setRows(res.rows.map(toEditableRow))
      setStep('preview')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось прочитать файл')
    } finally {
      setLoading(false)
    }
  }

  async function handleApply() {
    setError(null)
    setLoading(true)
    try {
      const res = await applyImport(buildApplyRows(rows))
      setResult(res)
      setStep('result')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось импортировать товары')
    } finally {
      setLoading(false)
    }
  }

  const includedCount = rows.filter((r) => r.included && r.action !== 'skip').length

  return (
    <Modal
      title={`Импорт товаров из ${format === 'csv' ? 'CSV' : 'Excel'}`}
      onClose={onClose}
      size={step === 'preview' ? 'full' : 'wide'}
      footer={
        step === 'preview' ? (
          <Button onClick={handleApply} disabled={loading || includedCount === 0}>
            {loading ? 'Импорт…' : `Импортировать ${includedCount} товаров`}
          </Button>
        ) : step === 'upload' ? (
          <Button onClick={handlePreview} disabled={!file || loading}>
            {loading ? 'Загрузка…' : 'Продолжить'}
          </Button>
        ) : (
          <Button
            onClick={() => {
              onDone()
              onClose()
            }}
          >
            Готово
          </Button>
        )
      }
    >
      <div className={layoutStyles.stack}>
        {error && <p className={layoutStyles.error}>{error}</p>}
        {step === 'upload' && <UploadStep format={format} file={file} onFileChange={setFile} />}
        {step === 'preview' && <PreviewStep rows={rows} setRows={setRows} categories={categories} units={units} />}
        {step === 'result' && result && <ResultStep result={result} />}
      </div>
    </Modal>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

const IMPORT_COLUMNS = [
  'Название',
  'Артикул',
  'Штрихкод',
  'Ед.изм.',
  'Категория',
  'Закупочная цена',
  'Розничная цена',
  'Маржа',
  'Мин.остаток',
]

function UploadStep({
  format,
  file,
  onFileChange,
}: {
  format: 'xlsx' | 'csv'
  file: File | null
  onFileChange: (file: File | null) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const extension = format === 'csv' ? '.csv' : '.xlsx'

  function handleFiles(files: FileList | null) {
    const picked = files?.[0]
    if (picked) onFileChange(picked)
  }

  return (
    <div className={layoutStyles.stack}>
      <div className={styles.importHint}>
        <span className={styles.importHintTitle}>
          <IconListDetails size={14} stroke={2} /> Формат колонок
        </span>
        <div className={styles.importHintColumns}>
          {IMPORT_COLUMNS.map((col, i) => (
            <span
              key={col}
              className={styles.importHintColumn}
              style={{ '--chip-delay': `${i * 30}ms` } as CSSProperties}
            >
              <span className={styles.importHintColumnIndex}>{i + 1}</span>
              {col}
            </span>
          ))}
        </div>
        <span className={styles.importHintNote}>Первая строка — заголовок, пропускается.</span>
      </div>

      <div
        className={[styles.dropzone, dragActive ? styles.dropzoneActive : '', file ? styles.dropzoneFilled : '']
          .filter(Boolean)
          .join(' ')}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragActive(true)
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragActive(false)
          handleFiles(e.dataTransfer.files)
        }}
        role="button"
        tabIndex={0}
        aria-label="Выбрать файл для импорта"
      >
        <input
          ref={inputRef}
          type="file"
          accept={extension}
          className={styles.dropzoneInput}
          onChange={(e) => handleFiles(e.target.files)}
        />
        {file ? (
          <div className={styles.dropzoneFile}>
            <span className={styles.dropzoneFileIcon}>
              <IconFileSpreadsheet size={28} stroke={1.6} />
            </span>
            <div className={styles.dropzoneFileInfo}>
              <span className={styles.dropzoneFileName}>{file.name}</span>
              <span className={styles.dropzoneFileMeta}>{formatFileSize(file.size)}</span>
            </div>
            <button
              type="button"
              className={styles.dropzoneClear}
              aria-label="Убрать файл"
              onClick={(e) => {
                e.stopPropagation()
                onFileChange(null)
                if (inputRef.current) inputRef.current.value = ''
              }}
            >
              <IconX size={16} stroke={1.8} />
            </button>
          </div>
        ) : (
          <div className={styles.dropzoneEmpty}>
            <span className={styles.dropzoneIcon}>
              <IconCloudUpload size={30} stroke={1.5} />
            </span>
            <span className={styles.dropzoneTitle}>
              Перетащите файл сюда или <span className={styles.dropzoneLink}>выберите на устройстве</span>
            </span>
            <span className={styles.dropzoneSubtitle}>
              Поддерживается {format === 'csv' ? 'CSV' : 'Excel (.xlsx)'}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function PreviewStep({
  rows,
  setRows,
  categories,
  units,
}: {
  rows: EditableRow[]
  setRows: React.Dispatch<React.SetStateAction<EditableRow[]>>
  categories: Category[]
  units: Unit[]
}) {
  const matchCount = rows.filter((r) => r.status !== 'no_match').length
  const [appliedNotice, setAppliedNotice] = useState<string | null>(null)
  const [lastBulkLabel, setLastBulkLabel] = useState<string | null>(null)
  const noticeTimerRef = useRef<number | null>(null)

  function updateRow(id: string, patch: Partial<EditableRow>) {
    setRows((rs) => rs.map((r) => (r.clientRowId === id ? { ...r, ...patch } : r)))
  }

  function applyBulkAction(action: ImportAction, label: string) {
    let affected = 0
    setRows((rs) =>
      rs.map((r) => {
        const isMatchStatus = r.status === 'match' || r.status === 'ambiguous_match'
        if (!isMatchStatus || r.actionTouched) return r
        affected += 1
        return { ...r, action }
      }),
    )
    setLastBulkLabel(label)
    setAppliedNotice(
      affected > 0
        ? `Применено «${label}» к ${affected} ${plural(affected, ['товару', 'товарам', 'товарам'])}`
        : 'Нет строк для применения',
    )
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current)
    noticeTimerRef.current = window.setTimeout(() => setAppliedNotice(null), 2600)
  }

  return (
    <>
      {matchCount > 0 && (
        <div className={styles.importToolbar}>
          <div>
            <h4 className={styles.importToolbarTitle}>Найдено совпадений: {matchCount}</h4>
            <span className={styles.importToolbarHint}>Применить ко всем сразу (кроме изменённых вручную)</span>
          </div>
          <div className={styles.importToolbarActions}>
            {appliedNotice && (
              <span key={appliedNotice} className={styles.importToolbarNotice}>
                <IconCircleCheck size={14} stroke={2} />
                {appliedNotice}
              </span>
            )}
            <DropdownMenu
              align="right"
              trigger={
                <Button variant="secondary">
                  {lastBulkLabel ?? 'Массовое действие'} <IconChevronDown size={14} stroke={1.8} />
                </Button>
              }
              items={[
                {
                  key: 'update',
                  label: 'Заменить существующий',
                  onSelect: () => applyBulkAction('update', 'Заменить существующий'),
                },
                {
                  key: 'update-price',
                  label: 'Обновить цену',
                  onSelect: () => applyBulkAction('update', 'Обновить цену'),
                },
                { key: 'skip', label: 'Пропустить', onSelect: () => applyBulkAction('skip', 'Пропустить') },
                {
                  key: 'create',
                  label: 'Создать новый',
                  onSelect: () => applyBulkAction('create', 'Создать новый'),
                },
              ]}
            />
          </div>
        </div>
      )}
      <div className={styles.importCardList}>
        {rows.map((row, i) => (
          <PreviewRowEditor
            key={row.clientRowId}
            row={row}
            index={i}
            categories={categories}
            units={units}
            onChange={(patch) => updateRow(row.clientRowId, patch)}
          />
        ))}
      </div>
    </>
  )
}

function matchLabel(by: 'barcode' | 'sku' | 'name') {
  return by === 'barcode' ? 'штрихкоду' : by === 'sku' ? 'артикулу' : 'названию'
}

function MatchBadge({ status }: { status: ImportMatchStatus }) {
  if (status === 'no_match') return <span className="badge">Новый товар</span>
  if (status === 'match') return <span className="badge accent">Совпадение</span>
  return <span className="badge warning">Неоднозначно</span>
}

const ACTION_LABELS: Record<ImportAction, string> = {
  create: 'Создать новый',
  update: 'Заменить существующий',
  skip: 'Пропустить',
}

function PreviewRowEditor({
  row,
  index,
  categories,
  units,
  onChange,
}: {
  row: EditableRow
  index: number
  categories: Category[]
  units: Unit[]
  onChange: (patch: Partial<EditableRow>) => void
}) {
  const needsAttention = row.parseError !== null || row.status === 'ambiguous_match'
  const [expanded, setExpanded] = useState(needsAttention)

  const bestCandidate =
    row.candidates.find((c) => c.product.id === row.selectedCandidateProductId) ??
    row.candidates[0]

  function hint(field: keyof ExistingProductSnapshot, current: string) {
    if (!bestCandidate) return null
    const was = String(bestCandidate.product[field])
    return was !== current ? <span className={styles.importFieldHint}>было: {was}</span> : null
  }

  return (
    <div
      className={[styles.importCard, styles.importCardIn, row.parseError ? styles.importCardError : ''].join(' ')}
      style={{ '--row-delay': `${Math.min(index, 12) * 25}ms` } as CSSProperties}
    >
      <div className={styles.importCardHead}>
        <input
          type="checkbox"
          checked={row.included}
          onChange={(e) => onChange({ included: e.target.checked })}
          aria-label="Включить в импорт"
          className={styles.importCardCheckbox}
        />
        <button
          type="button"
          className={styles.importCardSummary}
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          <span className={styles.importCardName}>{row.name || 'Без названия'}</span>
          {!expanded && (
            <span className={styles.importCardSummaryPrices}>
              {row.purchasePrice && <span>{row.purchasePrice} ₽</span>}
              {row.retailPrice && <span className={styles.importCardSummaryRetail}>{row.retailPrice} ₽</span>}
            </span>
          )}
          {(row.status === 'match' || row.status === 'ambiguous_match') && (
            <span
              key={row.action}
              className={[styles.importCardActionBadge, styles.importCardActionBadgeIn].join(' ')}
            >
              {ACTION_LABELS[row.action]}
            </span>
          )}
          <MatchBadge status={row.status} />
          <IconChevronDown
            size={16}
            stroke={1.8}
            className={[styles.importCardChevron, expanded ? styles.importCardChevronOpen : ''].join(' ')}
          />
        </button>
      </div>

      {row.parseError && <div className={styles.importCardErrorBanner}>{row.parseError}</div>}

      {expanded && (
        <div className={styles.importCardBody}>
          <label className={styles.importField}>
            <span className={styles.importFieldLabel}>Название</span>
            <input
              value={row.name}
              onChange={(e) => onChange({ name: e.target.value })}
              className={styles.importFieldInput}
              placeholder="Название товара"
            />
            {hint('name', row.name)}
          </label>

          <div className={styles.importFieldGrid}>
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Артикул</span>
              <input
                value={row.sku}
                onChange={(e) => onChange({ sku: e.target.value })}
                className={styles.importFieldInput}
              />
            </label>
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Штрихкод</span>
              <input
                value={row.barcode}
                onChange={(e) => onChange({ barcode: e.target.value })}
                className={styles.importFieldInput}
              />
            </label>
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Ед.изм.</span>
              <Select
                value={row.unitCode}
                onChange={(code) => onChange({ unitCode: code })}
                options={units.map((u) => ({ value: u.code, label: u.name }))}
              />
            </label>
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Мин.остаток</span>
              <input
                inputMode="decimal"
                value={row.minStock}
                onChange={(e) => {
                  const v = normalizeDecimalInput(e.target.value)
                  if (v !== null) onChange({ minStock: v })
                }}
                className={styles.importFieldInput}
              />
            </label>
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Закупочная цена</span>
              <input
                inputMode="decimal"
                value={row.purchasePrice}
                onChange={(e) => {
                  const v = normalizeDecimalInput(e.target.value)
                  if (v !== null) onChange({ purchasePrice: v })
                }}
                className={styles.importFieldInput}
              />
              {hint('purchase_price', row.purchasePrice)}
            </label>
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Розничная цена</span>
              <input
                inputMode="decimal"
                value={row.retailPrice}
                onChange={(e) => {
                  const v = normalizeDecimalInput(e.target.value)
                  if (v !== null) onChange({ retailPrice: v })
                }}
                className={styles.importFieldInput}
              />
              {hint('retail_price', row.retailPrice)}
            </label>
            <label className={`${styles.importField} ${styles.importFieldWide}`}>
              <span className={styles.importFieldLabel}>Категория</span>
              <Select
                value={row.categoryId ? String(row.categoryId) : ''}
                onChange={(v) => onChange({ categoryId: v ? Number(v) : null })}
                options={[{ value: '', label: 'Без категории' }, ...categoryOptions(categories)]}
              />
            </label>
          </div>

          {row.status === 'ambiguous_match' && (
            <label className={styles.importField}>
              <span className={styles.importFieldLabel}>Выбрать товар для замены</span>
              <Select
                value={row.selectedCandidateProductId ? String(row.selectedCandidateProductId) : ''}
                onChange={(v) => onChange({ selectedCandidateProductId: v ? Number(v) : null })}
                placeholder="Выберите товар"
                options={row.candidates.map((c) => ({
                  value: String(c.product.id),
                  label: `${c.product.name} (по ${matchLabel(c.matched_by)})`,
                }))}
              />
            </label>
          )}

          <label className={styles.importField}>
            <span className={styles.importFieldLabel}>Действие</span>
            <Select
              value={row.action}
              onChange={(action) => onChange({ action: action as ImportAction, actionTouched: true })}
              options={[
                { value: 'create', label: 'Создать новый' },
                {
                  value: 'update',
                  label: 'Заменить существующий',
                  disabled: row.status === 'ambiguous_match' && !row.selectedCandidateProductId,
                },
                { value: 'skip', label: 'Пропустить' },
              ]}
            />
          </label>
        </div>
      )}
    </div>
  )
}

function ResultStep({ result }: { result: ApplyImportResult }) {
  return (
    <div className={layoutStyles.stack}>
      <div className={styles.importResultBanner}>
        <IconCircleCheck size={32} stroke={1.6} className={styles.importResultBannerIcon} />
        <span className={styles.importResultBannerText}>Импорт завершён</span>
      </div>
      <div className={styles.importResultSummary}>
        <div className={styles.importResultStat}>
          <span className={styles.importResultStatValue}>{result.created}</span>
          <span className={styles.importResultStatLabel}>Создано</span>
        </div>
        <div className={styles.importResultStat}>
          <span className={styles.importResultStatValue}>{result.updated}</span>
          <span className={styles.importResultStatLabel}>Обновлено</span>
        </div>
        <div className={styles.importResultStat}>
          <span className={styles.importResultStatValue}>{result.skipped}</span>
          <span className={styles.importResultStatLabel}>Пропущено</span>
        </div>
      </div>
      {result.errors.length > 0 && (
        <div className={styles.importErrorList}>
          <span className={styles.importErrorListTitle}>
            <IconAlertTriangle size={16} stroke={1.8} /> Ошибки ({result.errors.length})
          </span>
          {result.errors.map((e, i) => (
            <div key={i} className={styles.importErrorRow}>
              <span className={styles.importErrorRowNum}>{e.client_row_id.replace('row-', '')}</span>
              <span className={styles.importErrorRowMsg}>{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
