#!/usr/bin/env node
/**
 * Визуальная приёмка (блок 4.5): обход экранов Playwright’ом и поиск
 * горизонтального overflow, обрезанного текста, мелких зон касания и т.п.
 *
 * Не правит приложение — только читает и пишет отчёт.
 *
 * Запуск (фронт на :5173, API на :8000):
 *   cd frontend && node scripts/visual-audit.mjs
 *
 * Env:
 *   AUDIT_BASE_URL=http://localhost:5173
 *   AUDIT_OWNER_PHONE=+79281110001
 *   AUDIT_OWNER_PASSWORD=audit12345
 *   AUDIT_SELLER_PHONE=+79281110002
 *   AUDIT_SELLER_PASSWORD=audit12345
 *   AUDIT_STORE_SLUG=audit-vizual
 *   AUDIT_QUICK=1  — меньше ширин/тем (smoke)
 *   AUDIT_ONLY=profile,login — только эти маршруты (ключи из списков ниже);
 *     отчёт тогда пишется в docs/screens/visual-audit/, а не поверх VISUAL_AUDIT.md
 */

import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..', '..')
const OUT_DIR = path.join(ROOT, 'docs', 'screens', 'visual-audit')
const ONLY = process.env.AUDIT_ONLY ? new Set(process.env.AUDIT_ONLY.split(',')) : null
const REPORT_MD = ONLY
  ? path.join(ROOT, 'docs', 'screens', 'visual-audit', 'VISUAL_AUDIT_ONLY.md')
  : path.join(ROOT, 'docs', 'VISUAL_AUDIT.md')
const BASE = process.env.AUDIT_BASE_URL ?? 'http://localhost:5173'

const OWNER = {
  phone: process.env.AUDIT_OWNER_PHONE ?? '+79281110001',
  password: process.env.AUDIT_OWNER_PASSWORD ?? 'audit12345',
  role: 'owner',
}
const SELLER = {
  phone: process.env.AUDIT_SELLER_PHONE ?? '+79281110002',
  password: process.env.AUDIT_SELLER_PASSWORD ?? 'audit12345',
  role: 'seller',
}
const STORE = process.env.AUDIT_STORE_SLUG ?? 'audit-vizual'

const QUICK = process.env.AUDIT_QUICK === '1'

const VIEWPORTS = QUICK
  ? [
      { w: 375, h: 667 },
      { w: 412, h: 852 },
      { w: 1440, h: 900 },
    ]
  : [
      { w: 320, h: 568 },
      { w: 360, h: 568 },
      { w: 375, h: 667 },
      { w: 393, h: 852 },
      { w: 412, h: 852 },
      { w: 768, h: 1024 },
      { w: 1024, h: 768 },
      { w: 1440, h: 900 },
    ]

const THEMES = QUICK ? ['light'] : ['light', 'dark']

/** Кабинет — после логина */
const CABINET_ROUTES = [
  { key: 'sales', path: '/' },
  { key: 'sales-new', path: '/sales/new' },
  { key: 'products', path: '/products' },
  { key: 'products-new', path: '/products/new' },
  { key: 'stock', path: '/stock' },
  { key: 'stock-history', path: '/stock/history' },
  { key: 'orders', path: '/orders' },
  { key: 'orders-new', path: '/orders/new' },
  { key: 'orders-storefront', path: '/orders/storefront-requests' },
  { key: 'storefront-manage', path: '/storefront' },
  { key: 'tasks', path: '/tasks' },
  { key: 'debts', path: '/debts' },
  { key: 'debts-new', path: '/debts/new' },
  { key: 'clients', path: '/clients' },
  { key: 'analytics', path: '/analytics' },
  { key: 'employees', path: '/employees' },
  { key: 'profile', path: '/profile' },
]

const PUBLIC_ROUTES = [
  { key: 'login', path: '/login' },
  { key: 'privacy', path: '/privacy' },
  { key: 'admin-login', path: '/admin' },
  { key: 'marketplace', path: '/marketplace' },
  { key: 'marketplace-shops', path: '/marketplace/shops' },
  { key: 'store-catalog', path: `/store/${STORE}` },
  { key: 'store-cart', path: `/store/${STORE}/cart` },
  { key: 'store-favorites', path: `/store/${STORE}/favorites` },
  { key: 'store-login', path: `/store/${STORE}/login` },
  { key: 'account', path: '/account' },
  { key: 'not-found', path: '/this-route-does-not-exist-404' },
]

function slugify(s) {
  return String(s)
    .replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 80)
}

async function setTheme(page, theme) {
  await page.addInitScript((mode) => {
    try {
      localStorage.setItem('waysklad:theme-mode', mode)
    } catch {
      /* ignore */
    }
  }, theme)
}

async function loginCabinet(page, creds) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(200)
  const phoneDigits = creds.phone.replace(/\D/g, '').replace(/^7/, '')
  const phoneInput = page.locator('form input').first()
  await phoneInput.click()
  await phoneInput.fill('')
  await phoneInput.type(phoneDigits, { delay: 15 })
  await page.locator('form input[type="password"]').first().fill(creds.password)
  await page.locator('form button[type="submit"]').first().click()
  await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 20000 })
  await page.waitForTimeout(300)
}

/** Сбор проблем в контексте страницы */
async function collectIssues(page, { mobile }) {
  return page.evaluate(({ mobile }) => {
    const issues = []
    const vw = window.innerWidth
    const vh = window.innerHeight

    // 1) page horizontal scroll
    const doc = document.documentElement
    if (doc.scrollWidth > doc.clientWidth + 1) {
      issues.push({
        kind: 'page-h-scroll',
        selector: 'html',
        detail: `scrollWidth=${doc.scrollWidth} clientWidth=${doc.clientWidth}`,
        root: 'layout-overflow',
      })
    }

    const isVisible = (el) => {
      const st = getComputedStyle(el)
      if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return false
      const r = el.getBoundingClientRect()
      return r.width > 0 && r.height > 0
    }

    const cssPath = (el) => {
      if (el.id) return `#${CSS.escape(el.id)}`
      const parts = []
      let n = el
      for (let i = 0; n && i < 4; i++) {
        let part = n.tagName.toLowerCase()
        if (n.classList?.length) part += '.' + [...n.classList].slice(0, 2).join('.')
        parts.unshift(part)
        n = n.parentElement
      }
      return parts.join(' > ')
    }

    function guessRoot(el, kind) {
      const path = cssPath(el)
      if (/sectionTitle|salePageActions|headerActions/i.test(path)) return 'page-title-actions'
      if (/AppLayout|topbar|Topbar|GlobalSearch|NotificationBell|mobileHeader|MobileHeader/i.test(path))
        return 'cabinet-header'
      if (/PublicHeader|_header_/i.test(path) && /public|Public|store/i.test(path + location.pathname))
        return 'public-header'
      if (/bottomNav|BottomNav|navBar|sellFab|moreBtn|MobileNav|_bar_.*_item/i.test(path))
        return 'mobile-bottom-nav'
      if (/Onboarding|spotlight|onboarding/i.test(path)) return 'onboarding-tour'
      if (/Modal|Sheet|Drawer|dialog|role="dialog"/i.test(path)) return 'modal-sheet'
      if (/(^|[^\w])(table|Table|DataGrid)([^\w]|$)/.test(path)) return 'tables-mobile'
      if (/MobileDock|toast|Toast|offlineBadge/i.test(path)) return 'fixed-stacking'
      if (/EmptyState|empty-state/i.test(path)) return 'empty-state'
      if (kind === 'page-h-scroll') return 'layout-overflow'
      if (kind === 'input-font-ios-zoom') return 'form-controls'
      if (kind === 'touch-target') return 'touch-targets'
      if (kind === 'font-too-small') return 'typography-min'
      if (kind === 'clipped-text') return 'text-ellipsis'
      return 'misc'
    }

    const all = [...document.querySelectorAll('body *')].filter(isVisible)

    for (const el of all) {
      const r = el.getBoundingClientRect()
      const st = getComputedStyle(el)
      const tagName = el.tagName

      // Skip non-interactive chrome: svg guts, pure text wrappers inside buttons
      if (tagName === 'PATH' || tagName === 'CIRCLE' || tagName === 'LINE' || tagName === 'POLYLINE') continue
      if (tagName === 'SVG' && el.closest('button, a, [role="button"]')) continue
      // Login/register carousel: две формы рядом в треке — намеренный overflow
      if (el.closest('[class*="auth-form-track"], [class*="auth-form-viewport"]')) continue

      // 2) horizontal out of viewport only (vertical page scroll is normal)
      if (r.right > vw + 2 || r.left < -2) {
        if (r.width >= 2 && r.height >= 2 && !(st.boxShadow && st.boxShadow.includes('9999px'))) {
          // ignore full-bleed backgrounds that are intentionally vw-sized with subpixel
          if (!(r.left >= -1 && r.width <= vw + 4)) {
            issues.push({
              kind: 'out-of-viewport',
              selector: cssPath(el),
              detail: `rect=[${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}×${Math.round(r.height)}] vw=${vw}`,
              root: guessRoot(el, 'out-of-viewport'),
            })
          }
        }
      }

      // 3) clipped text without ellipsis
      const overflowX = st.overflowX
      const overflow = st.overflow
      const clipped =
        overflowX === 'hidden' ||
        overflowX === 'clip' ||
        overflow === 'hidden' ||
        overflow === 'clip'
      if (clipped && el.scrollWidth > el.clientWidth + 1) {
        const ellipsis = st.textOverflow === 'ellipsis'
        if (!ellipsis && (el.textContent || '').trim().length > 0) {
          issues.push({
            kind: 'clipped-text',
            selector: cssPath(el),
            detail: `scrollW=${el.scrollWidth} clientW=${el.clientWidth} text="${(el.textContent || '').trim().slice(0, 40)}"`,
            root: guessRoot(el, 'clipped-text'),
          })
        }
      }

      // 4) touch targets — only the outermost interactive control
      if (mobile) {
        const role = el.getAttribute('role')
        const isControl =
          tagName === 'BUTTON' ||
          tagName === 'A' ||
          (tagName === 'INPUT' && el.type !== 'hidden' && el.type !== 'checkbox' && el.type !== 'radio') ||
          tagName === 'SELECT' ||
          tagName === 'TEXTAREA' ||
          role === 'button'
        if (isControl && (r.width < 44 - 0.5 || r.height < 44 - 0.5)) {
          const parentBtn = el.closest('button, a, [role="button"]')
          if (parentBtn && parentBtn !== el) {
            /* child control — ignore */
          } else {
            issues.push({
              kind: 'touch-target',
              selector: cssPath(el),
              detail: `${Math.round(r.width)}×${Math.round(r.height)}`,
              root: guessRoot(el, 'touch-target'),
            })
          }
        }
      }

      // 5) font-size — only leaf text nodes' parents with own text, skip icons
      const fs = parseFloat(st.fontSize) || 0
      const ownText = [...el.childNodes]
        .filter((n) => n.nodeType === 3 && n.textContent.trim())
        .map((n) => n.textContent.trim())
        .join('')
      if (fs > 0 && fs < 12 && ownText.length > 0) {
        issues.push({
          kind: 'font-too-small',
          selector: cssPath(el),
          detail: `${fs}px «${ownText.slice(0, 30)}»`,
          root: guessRoot(el, 'font-too-small'),
        })
      }
      if (
        mobile &&
        (tagName === 'INPUT' || tagName === 'SELECT' || tagName === 'TEXTAREA') &&
        el.type !== 'checkbox' &&
        el.type !== 'radio' &&
        el.type !== 'hidden' &&
        fs > 0 &&
        fs < 16
      ) {
        issues.push({
          kind: 'input-font-ios-zoom',
          selector: cssPath(el),
          detail: `${fs}px (<16)`,
          root: 'form-controls',
        })
      }
    }

    // 6) fixed elements overlapping each other
    const fixed = all.filter((el) => {
      const p = getComputedStyle(el).position
      return p === 'fixed' || p === 'sticky'
    })
    for (let i = 0; i < fixed.length; i++) {
      for (let j = i + 1; j < fixed.length; j++) {
        const a = fixed[i].getBoundingClientRect()
        const b = fixed[j].getBoundingClientRect()
        const overlap =
          a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
        if (!overlap) continue
        const area =
          Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
          Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top))
        if (area < 200) continue
        // ignore nested fixed
        if (fixed[i].contains(fixed[j]) || fixed[j].contains(fixed[i])) continue
        issues.push({
          kind: 'fixed-overlap',
          selector: `${cssPath(fixed[i])} ∩ ${cssPath(fixed[j])}`,
          detail: `overlap≈${Math.round(area)}px²`,
          root: 'fixed-stacking',
        })
      }
    }

    // 7) modals / sheets — только настоящие dialog/aria-modal
    const dialogs = [
      ...document.querySelectorAll('[role="dialog"], [aria-modal="true"]'),
    ].filter(isVisible)
    for (const d of dialogs) {
      const r = d.getBoundingClientRect()
      if (r.width > vw - 8 || r.height > vh - 8) {
        issues.push({
          kind: 'modal-overflow',
          selector: cssPath(d),
          detail: `${Math.round(r.width)}×${Math.round(r.height)} vs ${vw}×${vh}`,
          root: 'modal-sheet',
        })
      }
      const actions = d.querySelector(
        '[class*="actions"], [class*="footer"], [class*="Actions"], [class*="Footer"], [class*="modal-footer"]',
      )
      if (actions) {
        const ar = actions.getBoundingClientRect()
        if (ar.bottom > vh + 2 || ar.top < -2) {
          issues.push({
            kind: 'modal-actions-offscreen',
            selector: cssPath(actions),
            detail: `bottom=${Math.round(ar.bottom)} vh=${vh}`,
            root: 'modal-sheet',
          })
        }
      }
    }

    // de-dupe by kind+selector+detail prefix
    const seen = new Set()
    const unique = []
    for (const iss of issues) {
      const k = `${iss.kind}|${iss.selector}|${iss.detail.slice(0, 60)}`
      if (seen.has(k)) continue
      seen.add(k)
      unique.push(iss)
    }
    return unique
  }, { mobile })
}

async function openInteractiveStates(page, role) {
  const states = []

  // More sheet
  const moreBtn = page.locator('[data-onboarding-more], button:has-text("Ещё")').first()
  if (await moreBtn.isVisible().catch(() => false)) {
    await moreBtn.click().catch(() => {})
    await page.waitForTimeout(300)
    states.push('more-sheet')
    await page.keyboard.press('Escape').catch(() => {})
    await page.waitForTimeout(200)
  }

  // Notifications
  const bell = page.locator('[aria-label*="ведомлен"], button:has([class*="bell"]), [class*="NotificationBell"] button').first()
  if (await bell.isVisible().catch(() => false)) {
    await bell.click().catch(() => {})
    await page.waitForTimeout(300)
    states.push('notifications')
    await page.keyboard.press('Escape').catch(() => {})
    await page.waitForTimeout(150)
  }

  if (role === 'owner' || role === 'seller') {
    // On sales/new — try credit payment UI
    if (page.url().includes('/sales/new')) {
      const credit = page.locator('button:has-text("В долг"), label:has-text("В долг"), [role="radio"]:has-text("В долг")').first()
      if (await credit.isVisible().catch(() => false)) {
        await credit.click().catch(() => {})
        await page.waitForTimeout(200)
        states.push('sale-credit')
      }
    }
  }

  return states
}

async function runOnboardingSteps(page, viewport, theme, role, allIssues) {
  // Force-start tour via session + reload only for owner on products
  await page.evaluate(() => {
    sessionStorage.setItem('waysklad:onboarding-pending', '1')
    // clear done flag for current user patterns
    for (const k of Object.keys(localStorage)) {
      if (k.startsWith('waysklad:onboarding-done')) localStorage.removeItem(k)
    }
  })
  // Context only auto-starts for owner after register pending — call start if exposed
  // Navigate home and inject start by clicking nothing — use evaluate to dispatch
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' }).catch(() => {})
  await page.waitForTimeout(500)

  // Try to find overlay; if not, skip tour (can't start without React start())
  const hasOverlay = await page.locator('text=Шаг 1 из').first().isVisible().catch(() => false)
  if (!hasOverlay) {
    // Mark pending and reload after setting — OnboardingProvider checks pending on mount for owner
    await page.reload({ waitUntil: 'networkidle' }).catch(() => {})
    await page.waitForTimeout(600)
  }

  for (let step = 1; step <= 6; step++) {
    const visible = await page.locator(`text=Шаг ${step} из`).first().isVisible().catch(() => false)
    if (!visible) break
    const key = `onboarding-step-${step}`
    const issues = await collectIssues(page, { mobile: viewport.w < 900 })
    for (const iss of issues) {
      allIssues.push({
        ...iss,
        page: key,
        path: page.url(),
        width: viewport.w,
        height: viewport.h,
        theme,
        role,
        state: 'tour',
      })
    }
    const shotName = `${role}-${theme}-${viewport.w}x${viewport.h}-${key}.png`
    await page.screenshot({ path: path.join(OUT_DIR, shotName), fullPage: false }).catch(() => {})
    const next = page.locator('button:has-text("Дальше"), button:has-text("Начать"), button:has-text("Завершить")').last()
    if (await next.isVisible().catch(() => false)) {
      await next.click().catch(() => {})
      await page.waitForTimeout(500)
    } else break
  }
}

async function auditRoute(page, route, viewport, theme, role, allIssues) {
  const mobile = viewport.w < 900
  try {
    await page.goto(`${BASE}${route.path}`, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForTimeout(400)
  } catch (e) {
    allIssues.push({
      kind: 'nav-error',
      selector: 'page',
      detail: String(e.message || e).slice(0, 120),
      root: 'misc',
      page: route.key,
      path: route.path,
      width: viewport.w,
      height: viewport.h,
      theme,
      role,
      state: 'load',
    })
    return
  }

  let issues = []
  try {
    issues = await collectIssues(page, { mobile })
  } catch (e) {
    allIssues.push({
      kind: 'collect-error',
      selector: 'page',
      detail: String(e.message || e).slice(0, 120),
      root: 'misc',
      page: route.key,
      path: route.path,
      width: viewport.w,
      height: viewport.h,
      theme,
      role,
      state: 'default',
    })
    return
  }
  for (const iss of issues) {
    allIssues.push({
      ...iss,
      page: route.key,
      path: route.path,
      width: viewport.w,
      height: viewport.h,
      theme,
      role,
      state: 'default',
    })
  }

  // Interactive states only on hub routes (avoids OOM + noise)
  const openStates =
    route.key === 'sales' ||
    route.key === 'products' ||
    route.key === 'sales-new' ||
    route.key === 'debts'
  if (openStates) {
    try {
      const states = await openInteractiveStates(page, role)
      for (const st of states) {
        const moreIssues = await collectIssues(page, { mobile })
        for (const iss of moreIssues) {
          allIssues.push({
            ...iss,
            page: route.key,
            path: route.path,
            width: viewport.w,
            height: viewport.h,
            theme,
            role,
            state: st,
          })
        }
      }
    } catch {
      /* page may navigate away */
    }
  }

  // Screenshot key mobile widths always; others only if high-signal roots
  const highSignal = issues.some((i) =>
    [
      'page-title-actions',
      'cabinet-header',
      'mobile-bottom-nav',
      'modal-sheet',
      'layout-overflow',
      'empty-state',
      'onboarding-tour',
      'fixed-stacking',
    ].includes(i.root),
  )
  const shot =
    (viewport.w === 375 && theme === 'light') ||
    (highSignal && [320, 375, 412].includes(viewport.w))
  if (shot) {
    const name = `${role}-${theme}-${viewport.w}x${viewport.h}-${slugify(route.key)}.png`
    await page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false }).catch(() => {})
  }
}

function buildReport(allIssues) {
  // group by root
  const byRoot = new Map()
  for (const iss of allIssues) {
    const list = byRoot.get(iss.root) || []
    list.push(iss)
    byRoot.set(iss.root, list)
  }
  const roots = [...byRoot.entries()].sort((a, b) => b[1].length - a[1].length)

  const lines = []
  lines.push('# Визуальный аудит (блок 4.5)')
  lines.push('')
  lines.push(`Дата: ${new Date().toISOString()}`)
  lines.push(`База: \`${BASE}\``)
  lines.push(`Всего проблем (с повторами по ширинам/темам): **${allIssues.length}**`)
  lines.push(`Уникальных корней: **${roots.length}**`)
  lines.push('')
  lines.push('## Топ корней')
  lines.push('')
  lines.push('| # | Корень | Кол-во |')
  lines.push('|---|--------|--------|')
  roots.slice(0, 15).forEach(([root, list], i) => {
    lines.push(`| ${i + 1} | \`${root}\` | ${list.length} |`)
  })
  lines.push('')
  lines.push('## Таблица проблем')
  lines.push('')
  lines.push('| Страница / состояние | Ширина | Тема | Роль | Проблема | Элемент | Деталь | Корень |')
  lines.push('|---------------------|--------|------|------|----------|---------|--------|--------|')

  // collapse identical kind+selector+root across widths into one row with widths listed
  const collapsed = new Map()
  for (const iss of allIssues) {
    const k = `${iss.page}|${iss.state}|${iss.kind}|${iss.selector}|${iss.root}|${iss.role}|${iss.theme}`
    const cur = collapsed.get(k)
    if (cur) {
      cur.widths.add(iss.width)
    } else {
      collapsed.set(k, { ...iss, widths: new Set([iss.width]) })
    }
  }

  for (const iss of collapsed.values()) {
    const widths = [...iss.widths].sort((a, b) => a - b).join(', ')
    lines.push(
      `| ${iss.page} / ${iss.state} | ${widths} | ${iss.theme} | ${iss.role} | ${iss.kind} | \`${iss.selector.replace(/\|/g, '\\|')}\` | ${iss.detail.replace(/\|/g, '/').slice(0, 80)} | ${iss.root} |`,
    )
  }
  lines.push('')
  lines.push('## Скриншоты')
  lines.push('')
  lines.push('Файлы в `docs/screens/visual-audit/` (gitignored вместе с `docs/screens/`).')
  lines.push('')
  return { md: lines.join('\n'), roots, total: allIssues.length }
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true })
  const browser = await chromium.launch()
  const allIssues = []

  // Public routes (no auth)
  for (const theme of THEMES) {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: vp.w, height: vp.h },
        reducedMotion: 'reduce',
      })
      const page = await context.newPage()
      await setTheme(page, theme)
      for (const route of PUBLIC_ROUTES.filter((r) => !ONLY || ONLY.has(r.key))) {
        await auditRoute(page, route, vp, theme, 'anon', allIssues)
      }
      await context.close()
    }
  }

  // Cabinet per role
  for (const creds of [OWNER, SELLER]) {
    for (const theme of THEMES) {
      for (const vp of VIEWPORTS) {
        const context = await browser.newContext({
          viewport: { width: vp.w, height: vp.h },
          reducedMotion: 'reduce',
        })
        const page = await context.newPage()
        await setTheme(page, theme)
        try {
          await loginCabinet(page, creds)
        } catch (e) {
          allIssues.push({
            kind: 'login-failed',
            selector: '/login',
            detail: String(e.message || e),
            root: 'misc',
            page: 'login',
            path: '/login',
            width: vp.w,
            height: vp.h,
            theme,
            role: creds.role,
            state: 'auth',
          })
          await context.close()
          continue
        }

        for (const route of CABINET_ROUTES.filter((r) => !ONLY || ONLY.has(r.key))) {
          // seller may 403 on some — still scan UI
          await auditRoute(page, route, vp, theme, creds.role, allIssues)
        }

        if (!ONLY && creds.role === 'owner' && theme === 'light' && [375, 393, 412].includes(vp.w)) {
          await runOnboardingSteps(page, vp, theme, creds.role, allIssues)
        }

        await context.close()
      }
    }
  }

  await browser.close()

  const { md, roots, total } = buildReport(allIssues)
  await writeFile(REPORT_MD, md, 'utf8')

  console.log('\n=== VISUAL AUDIT ===')
  console.log(`Problems (with repeats): ${total}`)
  console.log('Top roots:')
  roots.slice(0, 10).forEach(([root, list], i) => {
    console.log(`  ${i + 1}. ${root} — ${list.length}`)
  })
  console.log(`Report: ${REPORT_MD}`)
  console.log(`Shots: ${OUT_DIR}`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
