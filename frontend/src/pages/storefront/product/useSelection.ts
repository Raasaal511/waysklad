import { useCallback, useState } from 'react'

/** Ключ строки выбора: id варианта или 'base' для товара без вариантов. */
export type SelectionKey = number | 'base'

/**
 * Покупатель может набрать сразу несколько вариантов разного количества.
 * Состояние — Map<ключ, qty>. 0 в карте не хранится (удаляем ключ при сбросе в 0).
 */
export function useSelection() {
  const [selection, setSelection] = useState<Map<SelectionKey, number>>(new Map())

  const setQty = useCallback((key: SelectionKey, qty: number) => {
    setSelection((prev) => {
      const next = new Map(prev)
      if (qty <= 0) next.delete(key)
      else next.set(key, qty)
      return next
    })
  }, [])

  const clear = useCallback(() => setSelection(new Map()), [])

  const totalQty = Array.from(selection.values()).reduce((sum, q) => sum + q, 0)
  const linesCount = selection.size

  return { selection, setQty, clear, totalQty, linesCount }
}
