#!/usr/bin/env node
/**
 * Живая проверка Web Push: настоящий Google Chrome (у Chromium из Playwright нет
 * ключей FCM), production-сборка с service worker, backend с VAPID-ключом.
 *
 * Цепочка: профиль → «Включить уведомления» → backend → FCM → service worker →
 * уведомление на экране; затем событие заявки с витрины; затем выход снимает
 * подписку. Скриншоты карточки — 375px, светлая и тёмная тема.
 *
 * Запуск (API на :8000 с VAPID_PRIVATE_KEY, `vite preview` на :4173):
 *   cd frontend && npm run build && npx vite preview --port 4173 &
 *   node scripts/push-e2e.mjs
 *
 * Env: PUSH_E2E_BASE_URL, PUSH_E2E_OUT (каталог скриншотов),
 *   PUSH_E2E_CUSTOMER_TOKEN_CMD — shell-команда, печатающая JWT покупателя
 *   (вход покупателя идёт через Telegram, в скрипте его не пройти); без неё
 *   шаг «заявка с витрины» пропускается. Пример — scripts/push-e2e-customer.sh.
 */

import { chromium } from 'playwright'
import { execSync } from 'node:child_process'
import { mkdir, mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const BASE = process.env.PUSH_E2E_BASE_URL ?? 'http://localhost:4173'
const OUT = process.env.PUSH_E2E_OUT ?? path.resolve('..', 'docs', 'screens', 'web-push')
const results = []

function check(name, ok, detail = '') {
  results.push({ name, ok })
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`)
}

async function api(pathname, { token, method = 'GET', body } = {}) {
  const response = await fetch(`${BASE}/api${pathname}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await response.text()
  return { status: response.status, json: text ? JSON.parse(text) : null }
}

async function registerOwner() {
  const phone = `+7928${String(Date.now()).slice(-7)}`
  const form = {
    shop_name: 'Push проверка',
    owner_name: 'Ахмед',
    phone,
    password: 'secret123',
    personal_data_consent: true,
  }
  const start = await api('/auth/register', { method: 'POST', body: form })
  if (start.status !== 201) throw new Error(`register ${start.status}: ${JSON.stringify(start.json)}`)
  // Шаг бота (кнопку «Поделиться номером» скрипт нажать не может) — тем же
  // use case, что и бот: см. PUSH_E2E_CONTACT_CMD, по умолчанию contact.sh рядом.
  const contact = process.env.PUSH_E2E_CONTACT_CMD ?? path.join(__dirname, 'push-e2e-contact.sh')
  const code = execSync(`${contact} ${start.json.token} ${phone}`).toString().trim()
  const done = await api('/auth/register/confirm', {
    method: 'POST',
    body: { token: start.json.token, code },
  })
  if (done.status !== 201) throw new Error(`confirm ${done.status}: ${JSON.stringify(done.json)}`)
  return done.json
}

/** Уведомления, которые сейчас показаны service worker'ом. */
async function shownNotifications(page) {
  return page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready
    return (await reg.getNotifications()).map((n) => ({ title: n.title, body: n.body, tag: n.tag }))
  })
}

async function waitForNotification(page, title, timeoutMs = 20000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const found = (await shownNotifications(page)).find((n) => n.title === title)
    if (found) return found
    await page.waitForTimeout(500)
  }
  return null
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const session = await registerOwner()
  const token = session.access_token

  // Постоянный профиль: в инкогнито (обычный launch) Chrome выключает Push API.
  const profileDir = await mkdtemp(path.join(tmpdir(), 'push-e2e-'))
  const context = await chromium.launchPersistentContext(profileDir, {
    channel: 'chrome',
    headless: true,
    viewport: { width: 375, height: 740 },
    deviceScaleFactor: 2,
    // Android-телефон: карточка пишет «на телефоне» и даёт подсказки для Android
    userAgent:
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36',
    hasTouch: true, // isMobile не ставим: эмуляция мобильного в Chrome отключает Notification API
  })
  await context.grantPermissions(['notifications'], { origin: BASE })
  await context.addInitScript(
    ([tok, user]) => {
      try {
        localStorage.setItem('access_token', tok)
        localStorage.setItem('user', JSON.stringify(user))
        localStorage.setItem('waysklad:onboarding-dismissed', '1')
      } catch {
        /* ignore */
      }
    },
    [token, session.user],
  )
  const page = context.pages()[0] ?? (await context.newPage())
  page.on('pageerror', (e) => console.log('pageerror:', e.message))
  page.on('console', (m) => m.type() === 'error' && console.log('console:', m.text()))

  await page.goto(`${BASE}/profile`, { waitUntil: 'networkidle' })
  await page.evaluate(() => navigator.serviceWorker.ready)
  await page.reload({ waitUntil: 'networkidle' }) // теперь страницей управляет SW

  const card = page.locator('h3', { hasText: /Уведомления на телефоне/ }).locator('xpath=ancestor::div[contains(@class,"card")][1]')
  await card.waitFor({ timeout: 10000 })
  await card.evaluate((el) => el.scrollIntoView({ block: 'center' }))
  check('карточка видна, кнопка «Включить»', await card.getByRole('button', { name: 'Включить уведомления' }).isVisible())
  for (const theme of ['light', 'dark']) {
    await page.evaluate((mode) => {
      localStorage.setItem('waysklad:theme-mode', mode)
      document.documentElement.dataset.theme = mode
    }, theme)
    await page.reload({ waitUntil: 'networkidle' })
    await card.evaluate((el) => el.scrollIntoView({ block: 'center' }))
    await card.screenshot({ path: path.join(OUT, `push-off-375-${theme}.png`) })
  }

  await card.getByRole('button', { name: 'Включить уведомления' }).click()
  await card.getByRole('status').waitFor({ timeout: 20000 })
  const noteText = await card.getByRole('status').textContent()
  check('пробное принято push-сервисом', noteText.includes('Отправили'), noteText)
  check('статус «Включены на этом устройстве»', await card.getByText('Включены на этом устройстве').isVisible())

  const test = await waitForNotification(page, 'Уведомления включены')
  check('пробное показано на экране (FCM → SW)', Boolean(test), JSON.stringify(test))
  await card.screenshot({ path: path.join(OUT, 'push-on-375-dark.png') })
  await page.evaluate(() => localStorage.setItem('waysklad:theme-mode', 'light'))
  await page.reload({ waitUntil: 'networkidle' })
  await card.evaluate((el) => el.scrollIntoView({ block: 'center' }))
  await card.screenshot({ path: path.join(OUT, 'push-on-375-light.png') })
  check('после перезагрузки статус сохраняется', await card.getByText('Включены на этом устройстве').isVisible())

  if (process.env.PUSH_E2E_CUSTOMER_TOKEN_CMD) {
    // настоящая заявка покупателя: витрина включена, товар с фото на витрине
    await api('/auth/shop', { token, method: 'PATCH', body: { name: 'Push проверка', storefront_enabled: true } })
    const created = await api('/products', {
      token,
      method: 'POST',
      body: { name: 'Мука высший сорт', purchase_price: '50', retail_price: '120' },
    })
    await api(`/products/${created.json.id}`, {
      token,
      method: 'PUT',
      body: { ...created.json, photo: 'https://example.com/flour.jpg', show_on_storefront: true },
    })
    const customerToken = execSync(process.env.PUSH_E2E_CUSTOMER_TOKEN_CMD).toString().trim()
    const request = await api(`/storefront/${session.shop_slug}/requests`, {
      token: customerToken,
      method: 'POST',
      body: { customer_name: 'Ахмед', items: [{ product_id: created.json.id, quantity: '2' }] },
    })
    check('заявка оформлена', request.status === 201, String(request.status))
    const order = await waitForNotification(page, 'Новая заявка с витрины')
    check('заявка с витрины пришла на экран', Boolean(order), JSON.stringify(order))
  }

  // выход снимает подписку браузера и на сервере
  const endpoint = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready
    return (await reg.pushManager.getSubscription())?.endpoint ?? null
  })
  check('подписка браузера есть до выхода', Boolean(endpoint), endpoint?.slice(0, 60))
  await page.evaluate(() => {
    const button = [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Выйти')
    button?.click()
  })
  await page.waitForTimeout(2500)
  const after = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready
    return (await reg.pushManager.getSubscription())?.endpoint ?? null
  })
  check('после выхода подписки браузера нет', after === null)
  const probe = await api('/notifications/push/test', { token, method: 'POST', body: { endpoint } })
  check('после выхода сервер не шлёт на это устройство', probe.json?.delivered === false, JSON.stringify(probe.json))

  await context.close()
  await rm(profileDir, { recursive: true, force: true })
  const failed = results.filter((r) => !r.ok)
  console.log(`\n${results.length - failed.length}/${results.length} проверок прошло`)
  process.exit(failed.length ? 1 : 0)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
