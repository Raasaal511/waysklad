import { useEffect, useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconX } from '@tabler/icons-react'
import { useOnboarding } from './OnboardingContext'
import { Button } from '../shared/ui/Button'
import styles from './OnboardingOverlay.module.css'

const PADDING = 8
const SIDE = 16
const CARD_GAP = 12

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

interface CardPos {
  top: number
  left: number
  width: number
  maxHeight: number
}

function isVisibleTarget(el: Element): boolean {
  const style = getComputedStyle(el)
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
    return false
  }
  let node: Element | null = el
  while (node && node !== document.body) {
    const s = getComputedStyle(node)
    if (s.display === 'none' || s.visibility === 'hidden') return false
    node = node.parentElement
  }
  const r = el.getBoundingClientRect()
  return r.width > 0 && r.height > 0
}

function findTarget(selector: string | null): Element | null {
  if (!selector) return null
  const nodes = document.querySelectorAll(`[data-onboarding="${CSS.escape(selector)}"]`)
  for (const el of nodes) {
    if (isVisibleTarget(el)) return el
  }
  return null
}

function viewportBox() {
  const vv = window.visualViewport
  if (vv) {
    return {
      top: vv.offsetTop,
      left: vv.offsetLeft,
      width: vv.width,
      height: vv.height,
    }
  }
  return { top: 0, left: 0, width: window.innerWidth, height: window.innerHeight }
}

function placeCard(target: Rect | null): CardPos {
  const vp = viewportBox()
  const narrow = vp.width < 600
  const width = narrow
    ? Math.max(0, vp.width - SIDE * 2)
    : Math.min(380, vp.width - SIDE * 2)
  const left = narrow
    ? vp.left + SIDE
    : vp.left + Math.min(Math.max(SIDE, target?.left ?? SIDE), vp.width - width - SIDE)

  if (!target) {
    return {
      top: vp.top + Math.max(SIDE, (vp.height - 220) / 2),
      left: vp.left + Math.max(SIDE, (vp.width - width) / 2),
      width,
      maxHeight: vp.height - SIDE * 2,
    }
  }

  const targetMidY = target.top + target.height / 2
  const placeAbove = targetMidY > vp.top + vp.height / 2
  const spaceAbove = target.top - vp.top - SIDE - CARD_GAP
  const spaceBelow = vp.top + vp.height - (target.top + target.height) - SIDE - CARD_GAP

  if (placeAbove && spaceAbove >= 120) {
    const maxHeight = Math.max(120, spaceAbove)
    const estimated = Math.min(maxHeight, 280)
    const top = Math.max(vp.top + SIDE, target.top - CARD_GAP - estimated)
    return { top, left, width, maxHeight }
  }

  const maxHeight = Math.max(120, spaceBelow)
  const top = Math.min(target.top + target.height + CARD_GAP, vp.top + vp.height - SIDE - 120)
  return { top, left, width, maxHeight }
}

/** Подсвечивает нужный элемент интерфейса (spotlight-вырез в затемнении) и
 * показывает рядом карточку с шагом тура. Следит за scroll/resize/DOM —
 * элемент может появиться не сразу (переход на страницу ещё грузится). */
export function OnboardingOverlay() {
  const { active, step, stepIndex, totalSteps, next, skip } = useOnboarding()
  const [rect, setRect] = useState<Rect | null>(null)
  const [card, setCard] = useState<CardPos | null>(null)

  useLayoutEffect(() => {
    if (!active || !step) {
      setRect(null)
      setCard(null)
      return
    }

    function measure() {
      const el = step!.target ? findTarget(step!.target) : null
      if (!el) {
        setRect(null)
        setCard(placeCard(null))
        return
      }
      const r = el.getBoundingClientRect()
      const nextRect = { top: r.top, left: r.left, width: r.width, height: r.height }
      setRect(nextRect)
      setCard(placeCard(nextRect))
    }

    measure()
    const pollId = window.setInterval(measure, 150)
    const stopPoll = window.setTimeout(() => window.clearInterval(pollId), 3500)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    const vv = window.visualViewport
    vv?.addEventListener('resize', measure)
    vv?.addEventListener('scroll', measure)
    return () => {
      window.clearInterval(pollId)
      window.clearTimeout(stopPoll)
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
      vv?.removeEventListener('resize', measure)
      vv?.removeEventListener('scroll', measure)
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

  if (!active || !step || !card) return null

  const hasSpotlight = rect != null

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
        style={{
          top: card.top,
          left: card.left,
          width: card.width,
          maxHeight: card.maxHeight,
        }}
      >
        <button type="button" className={styles.close} onClick={skip} aria-label="Пропустить тур">
          <IconX size={16} stroke={1.8} />
        </button>
        <span className={styles.progress}>
          Шаг {stepIndex + 1} из {totalSteps}
        </span>
        <div className={styles.scroll}>
          <h3 className={styles.title}>{step.title}</h3>
          <p className={styles.body}>{step.body}</p>
        </div>
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
