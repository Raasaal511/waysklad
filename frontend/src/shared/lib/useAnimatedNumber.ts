import { useEffect, useRef, useState } from 'react'

const DURATION_MS = 400
const EASE = (t: number) => 1 - Math.pow(1 - t, 3)

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Плавно прокручивает число от предыдущего значения к новому (как одометр),
 * вместо мгновенной подмены — используется в статах, которые меняются по клику
 * на фильтр (сумма выручки, кол-во продаж и т.п). */
export function useAnimatedNumber(target: number): number {
  const [value, setValue] = useState(target)
  const fromRef = useRef(target)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    if (target === fromRef.current) return
    if (prefersReducedMotion()) {
      fromRef.current = target
      setValue(target)
      return
    }
    const from = fromRef.current
    const start = performance.now()

    function tick(now: number) {
      const t = Math.min((now - start) / DURATION_MS, 1)
      const eased = EASE(t)
      setValue(from + (target - from) * eased)
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = target
      }
    }

    frameRef.current = requestAnimationFrame(tick)
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target])

  return value
}
