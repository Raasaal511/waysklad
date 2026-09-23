import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ThemeMode = 'light' | 'dark'
export type AccentColor = 'green' | 'blue' | 'terracotta' | 'violet'

interface ThemeState {
  mode: ThemeMode
  accent: AccentColor
  setMode: (mode: ThemeMode) => void
  setAccent: (accent: AccentColor) => void
}

const MODE_KEY = 'waysklad:theme-mode'
const ACCENT_KEY = 'waysklad:theme-accent'

const ThemeContext = createContext<ThemeState | null>(null)

/**
 * theme-color в index.html захардкожен под светлую зелёную тему и не менялся —
 * на тёмной теме или другом акценте цвет вкладки/статус-бара браузера не совпадал
 * с реальной шапкой (P6, «мелочи», favicon и theme-color). Берём фактический
 * var(--bg) после применения data-theme/data-accent — это и есть фон шапки.
 */
function syncThemeColorMeta() {
  const meta = document.querySelector('meta[name="theme-color"]')
  if (!meta) return
  const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
  if (bg) meta.setAttribute('content', bg)
}

function readMode(): ThemeMode {
  return localStorage.getItem(MODE_KEY) === 'dark' ? 'dark' : 'light'
}

function readAccent(): AccentColor {
  const stored = localStorage.getItem(ACCENT_KEY)
  return stored === 'blue' || stored === 'terracotta' || stored === 'violet' ? stored : 'green'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(readMode)
  const [accent, setAccent] = useState<AccentColor>(readAccent)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode)
    localStorage.setItem(MODE_KEY, mode)
    syncThemeColorMeta()
  }, [mode])

  useEffect(() => {
    document.documentElement.setAttribute('data-accent', accent)
    localStorage.setItem(ACCENT_KEY, accent)
    syncThemeColorMeta()
  }, [accent])

  return (
    <ThemeContext.Provider value={{ mode, accent, setMode, setAccent }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme должен использоваться внутри ThemeProvider')
  return ctx
}
