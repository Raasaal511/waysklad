import { forwardRef, useMemo, type ChangeEvent, type KeyboardEvent } from 'react'
import styles from './PhoneInput.module.css'

interface PhoneInputProps {
  value: string
  onChange: (value: string) => void
  required?: boolean
  tabIndex?: number
  placeholder?: string
  id?: string
}

function digitsAfterCountryCode(raw: string): string {
  let digits = raw.replace(/\D/g, '')
  if (digits.startsWith('8')) digits = `7${digits.slice(1)}`
  if (digits.startsWith('7')) digits = digits.slice(1)
  return digits.slice(0, 10)
}

function formatDigits(digits: string): string {
  const parts = []
  if (digits.length > 0) parts.push(digits.slice(0, 3))
  if (digits.length > 3) parts.push(digits.slice(3, 6))
  if (digits.length > 6) parts.push(digits.slice(6, 8))
  if (digits.length > 8) parts.push(digits.slice(8, 10))

  let result = ''
  if (parts[0] !== undefined) result += `(${parts[0]}`
  if (digits.length >= 3) result += ') '
  if (parts[1] !== undefined) result += parts[1]
  if (parts[2] !== undefined) result += `-${parts[2]}`
  if (parts[3] !== undefined) result += `-${parts[3]}`
  return result
}

export function digitsToE164(digits: string): string {
  return digits ? `+7${digits}` : ''
}

export const PhoneInput = forwardRef<HTMLInputElement, PhoneInputProps>(function PhoneInput(
  { value, onChange, required, tabIndex, placeholder = '(928) 000-00-00', id },
  ref,
) {
  const digits = useMemo(() => digitsAfterCountryCode(value), [value])
  const formatted = useMemo(() => formatDigits(digits), [digits])

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    onChange(digitsToE164(digitsAfterCountryCode(e.target.value)))
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key !== 'Backspace' && e.key !== 'Delete') return
    const input = e.currentTarget
    const { selectionStart, selectionEnd } = input
    if (selectionStart === null || selectionEnd === null || selectionStart !== selectionEnd) return

    if (e.key === 'Backspace') {
      if (selectionStart === 0) {
        e.preventDefault()
        return
      }
      const charBefore = formatted[selectionStart - 1]
      if (charBefore !== undefined && /\d/.test(charBefore)) return

      e.preventDefault()
      let cut = selectionStart - 1
      while (cut > 0 && !/\d/.test(formatted[cut - 1])) cut -= 1
      if (cut === 0) return
      const newDigits = digitsAfterCountryCode(formatted.slice(0, cut - 1) + formatted.slice(selectionStart))
      onChange(digitsToE164(newDigits))
      const newFormatted = formatDigits(newDigits)
      const caret = Math.min(cut - 1, newFormatted.length)
      requestAnimationFrame(() => input.setSelectionRange(caret, caret))
      return
    }

    // Delete
    if (selectionStart >= formatted.length) {
      e.preventDefault()
      return
    }
    const charAfter = formatted[selectionStart]
    if (/\d/.test(charAfter)) return

    e.preventDefault()
    let cut = selectionStart
    while (cut < formatted.length && !/\d/.test(formatted[cut])) cut += 1
    if (cut >= formatted.length) return
    const newDigits = digitsAfterCountryCode(formatted.slice(0, selectionStart) + formatted.slice(cut + 1))
    onChange(digitsToE164(newDigits))
    requestAnimationFrame(() => input.setSelectionRange(selectionStart, selectionStart))
  }

  return (
    <div className={styles['phone-input']}>
      <span className={styles['phone-input-prefix']}>+7</span>
      <input
        ref={ref}
        id={id}
        type="tel"
        inputMode="numeric"
        autoComplete="tel"
        className={styles['phone-input-field']}
        value={formatted}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        required={required}
        tabIndex={tabIndex}
      />
    </div>
  )
})
