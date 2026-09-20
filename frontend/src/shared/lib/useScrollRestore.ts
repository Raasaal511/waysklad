import { useEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

const STORAGE_KEY = 'waysklad:scroll-restore'

function readMap(): Record<string, number> {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '{}')
  } catch {
    return {}
  }
}

function writeMap(map: Record<string, number>) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map))
  } catch {
    /* приватный режим/заблокированное хранилище — просто не запомним позицию */
  }
}

/**
 * Восстанавливает позицию скролла при «назад» на списковых страницах публичной части
 * (маркетплейс, каталог магазина) — списки грузятся асинхронно, и на момент, когда браузер
 * штатно восстанавливает scrollY (popstate), страница ещё в состоянии skeleton и короче
 * целевой позиции: скролл проваливается на меньшую высоту и не доезжает до места, с которого
 * ушли (P6, найдено сквозным сценарием). BrowserRouter/History API не даёт хука на konец
 * реального рендера, поэтому храним позицию сами в sessionStorage по pathname+search
 * (переживает remount PublicLayout — он не Outlet, а отдельный экземпляр на каждый Route)
 * и досрочно откатываем нативное авто-восстановление (иначе оно и нативное будут спорить).
 *
 * @param ready — контент прогружен (не skeleton); позиция восстанавливается только тогда.
 */
export function useScrollRestore(ready: boolean) {
  const location = useLocation()
  const navType = useNavigationType()
  const key = `${location.pathname}${location.search}`
  const savedRef = useRef(false)

  // Отключаем нативное авто-восстановление один раз — иначе браузер выставит scrollY
  // раньше нашего эффекта (до прогрузки контента) и будет считаться, что скролл уже восстановлен.
  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual'
    }
  }, [])

  // Запоминаем позицию перед уходом со страницы (следующей навигацией) — сохраняем
  // непрерывно при скролле, не только один раз при размонтировании, иначе быстрый переход
  // (клик по карточке сразу после скролла) может уйти до срабатывания cleanup.
  useEffect(() => {
    function save() {
      const map = readMap()
      map[key] = window.scrollY
      writeMap(map)
    }
    window.addEventListener('scroll', save, { passive: true })
    return () => {
      save()
      window.removeEventListener('scroll', save)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // Восстанавливаем только на переход «назад/вперёд» (POP) и только когда контент готов —
  // на обычном переходе (PUSH) список открывается сверху, это отдельное намеренное поведение.
  useEffect(() => {
    if (navType !== 'POP' || !ready || savedRef.current) return
    const map = readMap()
    const y = map[key]
    if (typeof y === 'number') {
      savedRef.current = true
      window.scrollTo(0, y)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, navType, ready])

  // Сбрасываем флаг «уже восстановили» при смене страницы, чтобы следующий POP-переход
  // на другой список снова сработал.
  useEffect(() => {
    savedRef.current = false
  }, [key])
}
