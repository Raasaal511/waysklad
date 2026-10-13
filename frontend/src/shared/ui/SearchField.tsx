import { useRef } from 'react'
import { IconSearch, IconX } from '@tabler/icons-react'
import styles from './SearchField.module.css'

/**
 * Поле поиска: одна мягкая плашка без рамки, иконка внутри, крестик
 * очистки, Esc — тоже очистка. Обёртка сама рисует фокус (кольцо
 * акцентом), у самого input рамки и обводки нет — никакого «поля в поле».
 */
export function SearchField({
  value,
  onChange,
  placeholder = 'Поиск',
  className,
  autoFocus,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  autoFocus?: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <label className={[styles.field, className].filter(Boolean).join(' ')}>
      <IconSearch className={styles.icon} size={18} stroke={1.8} />
      <input
        ref={input}
        type="search"
        className={styles.input}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && value) {
            e.preventDefault()
            onChange('')
          }
        }}
        placeholder={placeholder}
        aria-label={placeholder}
        autoFocus={autoFocus}
        enterKeyHint="search"
      />
      <button
        type="button"
        className={`${styles.clear} ${value ? styles.clearVisible : ''}`}
        onClick={() => {
          onChange('')
          input.current?.focus()
        }}
        aria-label="Очистить поиск"
        tabIndex={value ? 0 : -1}
      >
        <IconX size={14} stroke={2.2} />
      </button>
    </label>
  )
}
