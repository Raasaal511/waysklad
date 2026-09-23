import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App.tsx'
import { initPwaInstall } from './shared/lib/pwaInstall'

// До рендера: событие установки может прийти раньше, чем откроют профиль.
initPwaInstall()

// После выката файлы старой версии удаляются с сервера. У того, у кого приложение было
// открыто, переход в ещё не открытый раздел падает на загрузке — вместо белого экрана
// перезагружаемся в новую версию. Не чаще раза в минуту, чтобы не зациклиться.
const STALE_RELOAD_KEY = 'waysklad:stale-chunk-reload'
window.addEventListener('vite:preloadError', (event) => {
  try {
    const last = Number(sessionStorage.getItem(STALE_RELOAD_KEY) ?? 0)
    if (Date.now() - last < 60_000) return
    sessionStorage.setItem(STALE_RELOAD_KEY, String(Date.now()))
  } catch {
    return // без sessionStorage не узнать, что уже перезагружались, — не рискуем циклом
  }
  event.preventDefault()
  window.location.reload()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
