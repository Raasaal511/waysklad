import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App.tsx'
import { initPwaInstall } from './shared/lib/pwaInstall'

// До рендера: событие установки может прийти раньше, чем откроют профиль.
initPwaInstall()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
