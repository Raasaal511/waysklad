import { useEffect, useRef, useState } from 'react'

const DURATION_MS = 450
// плавный ease-out (быстрый старт, мягкое затухание к концу) — ease-in-out на
// небольшой разнице значений ощущался как рывок в начале и "доводка" в конце
const EASE = (t: number) => 1 - Math.pow(1 - t, 3)

// Обновлять текст не чаще ~30 раз/сек — на 60fps каждый кадр меняет ширину
// глифов жирного крупного числа и подряд идущие микро-сдвиги читаются как "дрожание",
// хотя сама анимация плавная; при таком шаге глаз видит гладкое движение без тряски
const FRAME_INTERVAL_MS = 32

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
    let lastUpdate = 0

    function tick(now: number) {
      const t = Math.min((now - start) / DURATION_MS, 1)
      const eased = EASE(t)
      if (t >= 1 || now - lastUpdate >= FRAME_INTERVAL_MS) {
        lastUpdate = now
        setValue(from + (target - from) * eased)
      }
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
