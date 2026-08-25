import { useEffect, useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconX } from '@tabler/icons-react'
import { useOnboarding } from './OnboardingContext'
import { Button } from '../shared/ui/Button'
import styles from './OnboardingOverlay.module.css'

const PADDING = 8

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

function findTarget(selector: string | null): Element | null {
  if (!selector) return null
  return document.querySelector(`[data-onboarding="${CSS.escape(selector)}"]`)
}

/** Подсвечивает нужный элемент интерфейса (spotlight-вырез в затемнении) и
 * показывает рядом карточку с шагом тура. Следит за scroll/resize/DOM —
 * элемент может появиться не сразу (переход на страницу ещё грузится). */
export function OnboardingOverlay() {
  const { active, step, stepIndex, totalSteps, next, skip } = useOnboarding()
  const [rect, setRect] = useState<Rect | null>(null)

  useLayoutEffect(() => {
    if (!active || !step?.target) {
      setRect(null)
      return
    }
    function measure() {
      const el = findTarget(step!.target)
      if (!el) {
        setRect(null)
        return
      }
      const r = el.getBoundingClientRect()
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    }
    measure()
    // элемент может смонтироваться на тик позже (переход по роуту) — короткий поллинг
    const pollId = window.setInterval(measure, 150)
    const stopPoll = window.setTimeout(() => window.clearInterval(pollId), 2000)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      window.clearInterval(pollId)
      window.clearTimeout(stopPoll)
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [active, step])

  useEffect(() => {
    if (!active) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') skip()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [active, skip])

  if (!active || !step) return null

  const hasSpotlight = rect != null
  const cardStyle = hasSpotlight
    ? {
        top: Math.min(rect.top + rect.height + 12, window.innerHeight - 220),
        left: Math.min(Math.max(rect.left, 16), window.innerWidth - 336),
      }
    : undefined

  return createPortal(
    <div className={hasSpotlight ? styles.overlay : `${styles.overlay} ${styles.overlayDimmed}`}>
      {hasSpotlight && (
        <div
          className={styles.spotlight}
          style={{
            top: rect.top - PADDING,
            left: rect.left - PADDING,
            width: rect.width + PADDING * 2,
            height: rect.height + PADDING * 2,
          }}
        />
      )}
      <div
        className={hasSpotlight ? styles.card : styles.cardCentered}
        style={cardStyle}
      >
        <button type="button" className={styles.close} onClick={skip} aria-label="Пропустить тур">
          <IconX size={16} stroke={1.8} />
        </button>
        <span className={styles.progress}>
          Шаг {stepIndex + 1} из {totalSteps}
        </span>
        <h3 className={styles.title}>{step.title}</h3>
        <p className={styles.body}>{step.body}</p>
        <div className={styles.actions}>
          <button type="button" className={styles.skipLink} onClick={skip}>
            Пропустить тур
          </button>
          <Button onClick={next}>
            {stepIndex === 0 ? 'Начать' : stepIndex === totalSteps - 1 ? 'Завершить' : 'Дальше'}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
