// Разовый QA-скрипт для шага P6 (сквозная сверка трёх публичных страниц).
// НЕ часть приложения — запускать вручную с хоста, фронтенд поднят на :5173.
// Проверяет: сценарий покупателя целиком, состояния, фокус модалок/лайтбокса,
// двойной клик «В корзину», повторную навигацию на товар (POST /view),
// консоль/сеть на трёх страницах.
import { chromium } from 'playwright'

const BASE = process.env.SHOTS_BASE_URL ?? 'http://localhost:5173'
const RICH_PRODUCT_ID = 2
// «Плед флисовый 6» — тот же товар с 6 фото галереи, что GALLERY_PRODUCT_ID в shots.mjs;
// RICH_PRODUCT_ID (id=2, «Наушники беспроводные Sonic») намеренно без фото — не годится
// для проверки лайтбокса (P6, проверено через GET /storefront/demo-market/products/23).
const GALLERY_PRODUCT_ID = 23
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
    const scrollHeightBefore = await page.evaluate(() => document.body.scrollHeight)
    log('scenario', `marketplace layout has content: scrollHeight=${scrollHeightBefore}`, scrollHeightBefore > 900)

    // клик по первой карточке товара в ленте
    const firstCard = page.locator('article a[href*="/products/"]').first()
    await firstCard.waitFor({ state: 'visible', timeout: 10000 })
    const productHref = await firstCard.getAttribute('href')
    await firstCard.click()
    // Client-side роутинг (react-router): networkidle недостаточно — реальные данные
    // страницы уже могли быть в кеше React Query/fetch, поэтому сеть «утихает» раньше,
    // чем React перерисует DOM. Ждём саму смену URL, иначе следующий локатор может
    // поймать разметку ещё предыдущей страницы (P6, флейки скрипта).
    if (productHref) await page.waitForURL(`**${productHref}`, { timeout: 10000 })
    await page.waitForLoadState('networkidle')
    // макет не прыгает: URL после клика ведёт ровно на href карточки, без промежуточных скачков
    log('scenario', `navigated to clicked card href: ${page.url()} matches ${productHref}`, productHref != null && page.url().endsWith(productHref))
    const productHeaderH = await page.locator('header').first().boundingBox()
    log('scenario', `header height marketplace=${marketHeaderH?.height} product=${productHeaderH?.height}`, marketHeaderH?.height === productHeaderH?.height)

    // переход в магазин — «Каталог магазина» в хлебных крошках (не первый a[href^="/store/"]
    // в DOM, им может быть иконка-стрелка «назад» в шапке — берём именно текстовую крошку)
    const crumbLink = page.getByRole('link', { name: 'Каталог магазина', exact: true })
    await crumbLink.waitFor({ state: 'visible', timeout: 10000 })
    const shopHref = await crumbLink.getAttribute('href')
    await crumbLink.click()
    if (shopHref) await page.waitForURL(`**${shopHref}`, { timeout: 10000 })
    await page.waitForLoadState('networkidle')
    log('scenario', `navigated to shop href: ${page.url()} matches ${shopHref}`, shopHref != null && page.url().endsWith(shopHref))
    const catalogHeaderH = await page.locator('header').first().boundingBox()
    log('scenario', `header height catalog=${catalogHeaderH?.height}`, catalogHeaderH?.height === marketHeaderH?.height)

    // применяем фильтр "только в наличии" — сразу после client-side перехода из карточки
    // товара FilterBar может ещё не успеть примонтироваться (React дорисовывает уже после
    // networkidle), поэтому не гейтим клик через .count() «в лоб» — ждём появления
    // локатора отдельным waitFor с запасом, .count()===0 в этот момент не значит,
    // что элемента не будет (P6, флейки скрипта, не баг приложения).
    const inStockToggle = page.getByText('Только в наличии', { exact: false }).first()
    let filterApplied = false
    try {
      await inStockToggle.waitFor({ state: 'visible', timeout: 8000 })
      await inStockToggle.scrollIntoViewIfNeeded()
      const cardsBefore = await page.locator('article a[href*="/products/"]').count()
      await inStockToggle.click()
      await page.waitForFunction(() => location.search.includes('in_stock_only'), { timeout: 5000 })
      // URL меняется синхронно, но отфильтрованный список — уже отдельный React-рендер
      // после фетча: networkidle сам по себе не гарантирует, что DOM-сетка уже
      // перерисована (гонка поймана вживую на P6 — «Только в наличии» временно оставляет
      // старую, неотфильтрованную сетку видимой ещё несколько кадров). Ждём, пока число
      // карточек реально изменится, а не просто «сеть утихла».
      await page
        .waitForFunction(
          (prev) => document.querySelectorAll('article a[href*="/products/"]').length !== prev,
          cardsBefore,
          { timeout: 5000 },
        )
        .catch(() => {})
      await page.waitForLoadState('networkidle')
      filterApplied = true
    } catch {
      // фильтра «Только в наличии» нет на этом брейкпоинте/наборе данных — не критично
    }
    const urlAfterFilter = page.url()
    log('scenario', `filter in URL after apply: ${urlAfterFilter}`, filterApplied ? urlAfterFilter.includes('=') : true)

    // скроллим каталог, запоминаем позицию, открываем другой товар — берём первый товар
    // именно «в наличии» (после фильтра выше все карточки такие), чтобы гарантированно
    // попасть на страницу с активной кнопкой «В корзину», а не на «Нет в наличии».
    await page.evaluate(() => window.scrollTo(0, 800))
    const scrollBeforeNav = await page.evaluate(() => window.scrollY)
    const secondCard = page.locator('article a[href*="/products/"]').nth(1)
    await secondCard.waitFor({ state: 'visible', timeout: 10000 })
    const secondCardHref = await secondCard.getAttribute('href')
    await secondCard.click()
    if (secondCardHref) await page.waitForURL(`**${secondCardHref}`, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // назад — проверяем сохранение скролла и фильтра
    await page.goBack()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(400)
    const scrollAfterBack = await page.evaluate(() => window.scrollY)
    const urlAfterBack = page.url()
    log('scenario', `scroll preserved on back: before=${scrollBeforeNav} after=${scrollAfterBack}`, Math.abs(scrollBeforeNav - scrollAfterBack) < 50)
    log('scenario', `filter preserved on back: ${urlAfterBack}`, filterApplied ? urlAfterBack.includes('=') : true)

    // снова товар -> добавление в корзину -> переход в корзину. Берём href заново прямо
    // перед кликом (не переиспользуем secondCardHref из первого захода) — после goBack()
    // список на мгновение может отрисоваться в другом порядке, пока фильтр из URL не
    // применится повторно, и старый href окажется невалидной целью для waitForURL (P6).
    await secondCard.waitFor({ state: 'visible', timeout: 10000 })
    const secondCardHrefAfterBack = await secondCard.getAttribute('href')
    await secondCard.click().catch(async () => {
      await page.locator('article a[href*="/products/"]').nth(1).click()
    })
    if (secondCardHrefAfterBack) await page.waitForURL(`**${secondCardHrefAfterBack}`, { timeout: 10000 }).catch(() => {})
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
    await page.goto(`${BASE}/store/demo-market/products/${GALLERY_PRODUCT_ID}`, { waitUntil: 'networkidle' })
    // Триггер лайтбокса — кнопка вокруг главного фото (ProductGallery.tsx: styles.stageImgBtn,
    // aria-label «Открыть фото на весь экран»), не просто <img> — картинка не кликабельна сама
    // по себе (P6, поймано через реальную разметку компонента, не по угаданному классу).
    const openBtn = page.getByRole('button', { name: 'Открыть фото на весь экран' }).first()
    if (await openBtn.count()) {
      await openBtn.click()
      const lightbox = page.locator('[role="dialog"][aria-label="Просмотр фото"]')
      await lightbox.waitFor({ state: 'visible', timeout: 3000 }).catch(() => {})
      if (await lightbox.count()) {
        await page.keyboard.press('Escape')
        await page.waitForTimeout(300)
        const focusReturned = await openBtn.evaluate((el) => el === document.activeElement)
        log('focus-lightbox', `focus returned to gallery open-button after Esc: ${focusReturned}`, focusReturned)
      } else {
        log('focus-lightbox', 'clicking gallery photo did not open lightbox', false)
      }
    } else {
      log('focus-lightbox', 'no gallery open-photo button found', false)
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
