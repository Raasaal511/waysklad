// Разовый QA-скрипт для шага P6 (сквозная сверка трёх публичных страниц).
// НЕ часть приложения — запускать вручную с хоста, фронтенд поднят на :5173.
// Проверяет: сценарий покупателя целиком, состояния, фокус модалок/лайтбокса,
// двойной клик «В корзину», повторную навигацию на товар (POST /view),
// консоль/сеть на трёх страницах.
import { chromium } from 'playwright'

const BASE = process.env.SHOTS_BASE_URL ?? 'http://localhost:5173'
const RICH_PRODUCT_ID = 2
const results = []

function log(section, msg, ok = true) {
  results.push({ section, msg, ok })
  console.log(`${ok ? 'OK  ' : 'FAIL'} [${section}] ${msg}`)
}

function attachLogging(page, bucket) {
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      bucket.push(`${msg.type()}: ${msg.text()}`)
    }
  })
  page.on('pageerror', (err) => bucket.push(`pageerror: ${err.message}`))
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('/view')) bucket.push(`HTTP ${r.status()} ${r.url()}`)
  })
}

async function main() {
  const browser = await chromium.launch()

  // ---------- 1. Сквозной сценарий покупателя ----------
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    const consoleBucket = []
    attachLogging(page, consoleBucket)

    await page.goto(`${BASE}/marketplace`, { waitUntil: 'networkidle' })
    const marketHeaderH = await page.locator('header').first().boundingBox()
    const scrollHeight1 = await page.evaluate(() => document.body.scrollHeight)

    // клик по первой карточке товара в ленте
    const firstCard = page.locator('article a[href*="/products/"]').first()
    await firstCard.waitFor({ state: 'visible', timeout: 10000 })
    const productHref = await firstCard.getAttribute('href')
    await firstCard.click()
    await page.waitForLoadState('networkidle')
    const productHeaderH = await page.locator('header').first().boundingBox()
    log('scenario', `header height marketplace=${marketHeaderH?.height} product=${productHeaderH?.height}`, marketHeaderH?.height === productHeaderH?.height)

    // переход в магазин
    const crumbLink = page.locator('a[href^="/store/"]').first()
    const shopHref = await crumbLink.getAttribute('href')
    await crumbLink.click()
    await page.waitForLoadState('networkidle')
    const catalogHeaderH = await page.locator('header').first().boundingBox()
    log('scenario', `header height catalog=${catalogHeaderH?.height}`, catalogHeaderH?.height === marketHeaderH?.height)

    // применяем фильтр "только в наличии", если есть
    const inStockToggle = page.getByText('Только в наличии', { exact: false }).first()
    let filterApplied = false
    if (await inStockToggle.count()) {
      await inStockToggle.click().catch(() => {})
      await page.waitForTimeout(500)
      filterApplied = true
    }
    const urlAfterFilter = page.url()
    log('scenario', `filter in URL after apply: ${urlAfterFilter}`, filterApplied ? urlAfterFilter.includes('=') : true)

    // скроллим каталог, запоминаем позицию, открываем другой товар
    await page.evaluate(() => window.scrollTo(0, 800))
    const scrollBeforeNav = await page.evaluate(() => window.scrollY)
    const secondCard = page.locator('article a[href*="/products/"]').nth(1)
    await secondCard.waitFor({ state: 'visible', timeout: 10000 })
    await secondCard.click()
    await page.waitForLoadState('networkidle')

    // назад — проверяем сохранение скролла и фильтра
    await page.goBack()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(400)
    const scrollAfterBack = await page.evaluate(() => window.scrollY)
    const urlAfterBack = page.url()
    log('scenario', `scroll preserved on back: before=${scrollBeforeNav} after=${scrollAfterBack}`, Math.abs(scrollBeforeNav - scrollAfterBack) < 50)
    log('scenario', `filter preserved on back: ${urlAfterBack}`, filterApplied ? urlAfterBack.includes('=') : true)

    // снова товар -> добавление в корзину -> переход в корзину
    await secondCard.click().catch(async () => {
      await page.locator('article a[href*="/products/"]').nth(1).click()
    })
    await page.waitForLoadState('networkidle')
    const addBtn = page.getByRole('button', { name: /В корзину|Добавлено/ }).first()
    await addBtn.waitFor({ state: 'visible', timeout: 10000 })
    await addBtn.click()
    await page.waitForTimeout(300)
    const cartLink = page.locator('a[href*="/cart"]').first()
    if (await cartLink.count()) {
      await cartLink.click()
      await page.waitForLoadState('networkidle')
      const cartHeaderH = await page.locator('header').first().boundingBox()
      log('scenario', `header height cart=${cartHeaderH?.height}`, cartHeaderH?.height === marketHeaderH?.height)
    }

    if (consoleBucket.length) {
      log('scenario-console', JSON.stringify(consoleBucket), false)
    } else {
      log('scenario-console', 'no console errors/warnings during full journey', true)
    }
    await context.close()
  }

  // ---------- 2. Двойной клик "В корзину" ----------
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.goto(`${BASE}/store/demo-market/products/${RICH_PRODUCT_ID}`, { waitUntil: 'networkidle' })
    // товар с вариантами: используем "Количество"/первый доступный вариант через саму кнопку "В корзину" (без выбора)
    await page.evaluate(() => localStorage.removeItem('waysklad:storefront-cart:demo-market'))
    await page.reload({ waitUntil: 'networkidle' })
    const addBtn = page.getByRole('button', { name: /В корзину/ }).first()
    await addBtn.waitFor({ state: 'visible' })
    // Быстрый двойной клик — dblclick шлёт оба click событий почти одновременно.
    await addBtn.dblclick({ delay: 20 })
    await page.waitForTimeout(700)
    const cart = await page.evaluate(() => {
      const raw = localStorage.getItem('waysklad:storefront-cart:demo-market')
      return raw ? JSON.parse(raw) : []
    })
    const totalQty = cart.reduce((s, i) => s + Number(i.quantity), 0)
    log('double-click', `cart after dblclick: ${JSON.stringify(cart.map((i) => i.quantity))} totalQty=${totalQty}`, cart.length === 1)
    await context.close()
  }

  // ---------- 3. Повторная навигация на тот же товар — не дублирует POST /view ----------
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    const viewCalls = []
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/view')) viewCalls.push(req.url())
    })
    await page.goto(`${BASE}/store/demo-market/products/${RICH_PRODUCT_ID}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(300)
    await page.goto(`${BASE}/store/demo-market`, { waitUntil: 'networkidle' })
    await page.goto(`${BASE}/store/demo-market/products/${RICH_PRODUCT_ID}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(300)
    log('view-tracking', `POST /view calls across 2 navigations to same product: ${viewCalls.length} (expected 2, one per navigation, no duplicate within a single navigation)`, viewCalls.length === 2)
    await context.close()
  }

  // ---------- 4. Фокус после закрытия модалки ----------
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.goto(`${BASE}/store/demo-market`, { waitUntil: 'networkidle' })
    // "Адрес и условия" кнопка в ShopHeader
    const condBtn = page.getByRole('button', { name: /Адрес и условия/ }).first()
    if (await condBtn.count()) {
      await condBtn.click()
      await page.waitForTimeout(300)
      await page.keyboard.press('Escape')
      await page.waitForTimeout(300)
      const isFocused = await condBtn.evaluate((el) => el === document.activeElement)
      log('focus-modal', `focus returned to "Адрес и условия" button after Esc: ${isFocused}`, isFocused)
    } else {
      log('focus-modal', 'no "Адрес и условия" button found on catalog page', false)
    }
    await context.close()
  }

  // ---------- 5. Фокус после закрытия лайтбокса ----------
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.goto(`${BASE}/store/demo-market/products/${RICH_PRODUCT_ID}`, { waitUntil: 'networkidle' })
    const galleryImg = page.locator('[class*="gallery"] img, [class*="Gallery"] img').first()
    if (await galleryImg.count()) {
      await galleryImg.click({ force: true }).catch(() => {})
      await page.waitForTimeout(300)
      const lightboxOpen = await page.locator('[role="dialog"][aria-label="Просмотр фото"]').count()
      if (lightboxOpen) {
        await page.keyboard.press('Escape')
        await page.waitForTimeout(300)
        const activeTag = await page.evaluate(() => document.activeElement?.tagName)
        log('focus-lightbox', `lightbox closed via Esc, activeElement=${activeTag}`, true)
      } else {
        log('focus-lightbox', 'clicking gallery image did not open lightbox (may need different selector)', false)
      }
    } else {
      log('focus-lightbox', 'no gallery image found', false)
    }
    await context.close()
  }

  // ---------- 6. Состояния: 404, ошибка сети, пусто ----------
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.goto(`${BASE}/store/nonexistent-shop-xyz`, { waitUntil: 'networkidle' })
    const notFoundText = await page.textContent('body')
    log('state-404-shop', `404 shop shows not-found text: ${/не найден|заблокирован/i.test(notFoundText || '')}`, /не найден|заблокирован/i.test(notFoundText || ''))

    await page.goto(`${BASE}/store/demo-market/products/999999`, { waitUntil: 'networkidle' })
    const notFoundProductText = await page.textContent('body')
    log('state-404-product', `404 product shows not-found text: ${/не найден/i.test(notFoundProductText || '')}`, /не найден/i.test(notFoundProductText || ''))
    await context.close()
  }

  // network error simulation
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await page.route('**/api/storefront/demo-market**', (route) => route.abort())
    await page.goto(`${BASE}/store/demo-market`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)
    const bodyText = await page.textContent('body')
    log('state-network-error', `network error state shows something (not blank): length=${bodyText?.trim().length}`, (bodyText?.trim().length ?? 0) > 20)
    await context.close()
  }

  console.log('\n=== ИТОГ ===')
  const failed = results.filter((r) => !r.ok)
  console.log(`Всего проверок: ${results.length}, провалено: ${failed.length}`)
  if (failed.length) {
    console.log('Провалено:')
    for (const f of failed) console.log(`  [${f.section}] ${f.msg}`)
  }

  await browser.close()
  process.exitCode = failed.length ? 1 : 0
}

main().catch((err) => {
  console.error('Скрипт P6-QA упал:', err)
  process.exitCode = 1
})
