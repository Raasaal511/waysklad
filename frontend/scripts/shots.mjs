// Скриншоты публичных страниц ВайСклад для дизайн-работы (шаг P0 дизайн-системы
// публичных страниц). Обычный вспомогательный playwright-скрипт, НЕ часть
// приложения — запускать с хоста (не в docker), фронтенд должен быть уже
// поднят на http://localhost:5173 (docker-контейнер waysklad-frontend-1).
//
// Требует, чтобы backend/scripts/seed_public_demo.py уже был запущен —
// использует конкретные id товаров демо-магазина «Демо-маркет» (slug
// demo-market): товар с вариантами/скидкой/отзывами и простой товар без
// вариантов/фото/отзывов.
//
// Запуск:
//   cd frontend && node scripts/shots.mjs
//
// Печатает в конце: список созданных файлов и список ошибок консоли/сети,
// найденных на каждой странице (это часть отчёта P0, сами скриншоты на этом
// шаге не разбираются).

import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = path.resolve(__dirname, '..', '..', 'docs', 'screens')
const BASE_URL = process.env.SHOTS_BASE_URL ?? 'http://localhost:5173'

// id актуальны после backend/scripts/seed_public_demo.py (магазин demo-market):
// товар "Наушники беспроводные Sonic" (id=2) — варианты, скидка 25%, 20 отзывов;
// товар "Худи оверсайз 2" (id=9) — без вариантов, без фото, без отзывов.
const RICH_PRODUCT_ID = 2
const SIMPLE_PRODUCT_ID = 9
// доп. контрольные случаи для приёмки P4 (docs/PUBLIC_PAGES_FINISH_PROMPTS.md):
// "Плед флисовый 6" (id=23) — 6 фото, 8 вариантов, скидка, в наличии;
// "Туфли классические 4" (id=16) — без вариантов, 0 остаток («нет в наличии»);
// "Скотч" (id=1, магазин waysklad) — без вариантов, мин. заказ 5 шт · шаг 1.
const GALLERY_PRODUCT_ID = 23
const OUT_OF_STOCK_PRODUCT_ID = 16
const MIN_ORDER_PRODUCT_ID = 1

const PAGES = [
  { key: 'marketplace', path: '/marketplace' },
  // Режим каталога главной маркетплейса (шаг P5) — подборка «Скидки» через чип
  // SectionChips и поиск по запросу, оба переключают /marketplace в режим каталога.
  { key: 'marketplace-catalog-discount', path: '/marketplace?section=discount' },
  { key: 'marketplace-catalog-search', path: '/marketplace?q=%D1%84%D1%83%D1%82%D0%B1%D0%BE%D0%BB%D0%BA%D0%B0' },
  { key: 'marketplace-shops', path: '/marketplace/shops' },
  { key: 'store-catalog', path: '/store/demo-market' },
  { key: 'product-rich', path: `/store/demo-market/products/${RICH_PRODUCT_ID}` },
  { key: 'product-simple', path: `/store/demo-market/products/${SIMPLE_PRODUCT_ID}` },
  { key: 'product-gallery', path: `/store/demo-market/products/${GALLERY_PRODUCT_ID}` },
  { key: 'product-out-of-stock', path: `/store/demo-market/products/${OUT_OF_STOCK_PRODUCT_ID}` },
  { key: 'product-min-order', path: `/store/waysklad/products/${MIN_ORDER_PRODUCT_ID}` },
  { key: 'cart', path: '/store/demo-market/cart' },
]

const WIDTHS = [375, 768, 1440]
const THEMES = ['light', 'dark']
const VIEWPORT_HEIGHT = 900

async function waitForFonts(page) {
  await page.evaluate(() => document.fonts.ready).catch(() => {})
}

async function scrollToBottomAndBack(page) {
  await page.evaluate(async () => {
    const step = 600
    const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
    let last = -1
    // скроллим вниз пошагово, чтобы дать шанс сработать IntersectionObserver
    // ленивых блоков (похожие товары, лента отзывов и т.п. — см. F0-F8/B4)
    for (let i = 0; i < 40; i++) {
      window.scrollBy(0, step)
      await delay(120)
      const current = window.scrollY
      if (current === last) break
      last = current
    }
    await delay(300)
    window.scrollTo(0, 0)
    await delay(200)
  })
}

async function shootOne(browser, { key, path: pagePath }, width, theme, report) {
  const context = await browser.newContext({
    viewport: { width, height: VIEWPORT_HEIGHT },
    reducedMotion: 'reduce',
  })

  // тема хранится в localStorage под ключом waysklad:theme-mode ('dark'/'light') —
  // ThemeContext НЕ читает prefers-color-scheme, поэтому эмулируем через
  // addInitScript (выполняется до первого скрипта страницы), а не через
  // colorScheme контекста браузера (тот не сработал бы, см. ThemeContext.tsx)
  await context.addInitScript((mode) => {
    try {
      window.localStorage.setItem('waysklad:theme-mode', mode)
    } catch {
      // приватный режим/заблокированное хранилище — тема останется дефолтной
    }
  }, theme)

  const page = await context.newPage()

  const consoleErrors = []
  const failedRequests = []

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text())
    }
  })
  page.on('pageerror', (err) => {
    consoleErrors.push(`pageerror: ${err.message}`)
  })
  page.on('requestfailed', (request) => {
    failedRequests.push(
      `${request.method()} ${request.url()} — ${request.failure()?.errorText ?? 'unknown'}`
    )
  })
  page.on('response', (response) => {
    if (response.status() >= 400) {
      failedRequests.push(`${response.status()} ${response.url()}`)
    }
  })

  const url = `${BASE_URL}${pagePath}`
  const fileName = `${key}-${width}-${theme}.png`
  const filePath = path.join(OUT_DIR, fileName)

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 })
    await waitForFonts(page)
    await scrollToBottomAndBack(page)
    // дать networkidle ещё раз осесть после скролла (ленивые блоки могли
    // достучаться до API уже во время скролла)
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {})
    await page.screenshot({ path: filePath, fullPage: true })
    report.files.push(fileName)
  } catch (err) {
    report.pageFailures.push({ page: key, width, theme, error: String(err) })
  } finally {
    if (consoleErrors.length) {
      report.consoleErrors.push({ page: key, width, theme, errors: consoleErrors })
    }
    if (failedRequests.length) {
      report.failedRequests.push({ page: key, width, theme, requests: failedRequests })
    }
    await context.close()
  }
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true })

  const browser = await chromium.launch()
  const report = { files: [], consoleErrors: [], failedRequests: [], pageFailures: [] }

  for (const pageSpec of PAGES) {
    for (const width of WIDTHS) {
      for (const theme of THEMES) {
        await shootOne(browser, pageSpec, width, theme, report)
      }
    }
  }

  await browser.close()

  console.log('\n=== Файлы скриншотов ===')
  for (const file of report.files) {
    console.log(`  docs/screens/${file}`)
  }
  console.log(`\nВсего файлов: ${report.files.length} (ожидалось: ${PAGES.length * WIDTHS.length * THEMES.length})`)

  if (report.pageFailures.length) {
    console.log('\n=== Страницы, которые не удалось снять ===')
    for (const failure of report.pageFailures) {
      console.log(`  [${failure.page} ${failure.width} ${failure.theme}] ${failure.error}`)
    }
  }

  console.log('\n=== Ошибки консоли (console.error / pageerror) ===')
  if (!report.consoleErrors.length) {
    console.log('  Нет ошибок консоли.')
  } else {
    for (const entry of report.consoleErrors) {
      console.log(`  [${entry.page} ${entry.width} ${entry.theme}]`)
      for (const e of entry.errors) {
        console.log(`    - ${e}`)
      }
    }
  }

  console.log('\n=== Проваленные запросы / ответы >=400 (включая 404 по картинкам) ===')
  if (!report.failedRequests.length) {
    console.log('  Нет проваленных запросов.')
  } else {
    for (const entry of report.failedRequests) {
      console.log(`  [${entry.page} ${entry.width} ${entry.theme}]`)
      for (const r of entry.requests) {
        console.log(`    - ${r}`)
      }
    }
  }

  const hadProblems =
    report.pageFailures.length > 0 ||
    report.consoleErrors.length > 0 ||
    report.failedRequests.length > 0
  process.exitCode = hadProblems ? 1 : 0
}

main().catch((err) => {
  console.error('Скрипт скриншотов упал:', err)
  process.exitCode = 1
})
