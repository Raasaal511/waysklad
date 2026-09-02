import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import styles from './PillTabs.module.css'

export interface PillTabsProps<T extends string> {
  value: T
  options: readonly T[]
  labels: Record<T, string>
  onChange: (value: T) => void
  className?: string
}

/** Переключатель-«таблетка» с зелёным индикатором, который плавно перетекает
 * к активной кнопке (transform), а не гаснет/загорается на каждой кнопке отдельно. */
export function PillTabs<T extends string>({ value, options, labels, onChange, className }: PillTabsProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const [indicator, setIndicator] = useState<{ x: number; width: number } | null>(null)

  useLayoutEffect(() => {
    const container = containerRef.current
    const button = buttonRefs.current.get(value)
    if (!container || !button) return
    const containerRect = container.getBoundingClientRect()
    const buttonRect = button.getBoundingClientRect()
    setIndicator({ x: buttonRect.left - containerRect.left, width: buttonRect.width })
  }, [value, options])

  useEffect(() => {
    function handleResize() {
      const container = containerRef.current
      const button = buttonRefs.current.get(value)
      if (!container || !button) return
      const containerRect = container.getBoundingClientRect()
      const buttonRect = button.getBoundingClientRect()
      setIndicator({ x: buttonRect.left - containerRect.left, width: buttonRect.width })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [value])

  return (
    <div ref={containerRef} className={[styles['pill-tabs'], className].filter(Boolean).join(' ')}>
      {indicator && (
        <div
          className={styles['pill-tabs-indicator']}
          style={{ transform: `translateX(${indicator.x}px)`, width: indicator.width }}
        />
      )}
      {options.map((option) => (
        <button
          key={option}
          ref={(el) => {
            if (el) buttonRefs.current.set(option, el)
            else buttonRefs.current.delete(option)
          }}
          type="button"
          translate="no"
          className={[styles['pill-tabs-item'], value === option && styles['pill-tabs-item-active']]
            .filter(Boolean)
            .join(' ')}
          onClick={() => onChange(option)}
        >
          {labels[option]}
        </button>
      ))}
    </div>
  )
}
