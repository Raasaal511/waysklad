/**
 * Приёмка TASK_PUBLIC_UNIFY п.7: сценарий + скриншоты 375/1440 светлая/тёмная.
 * Запуск: npx playwright test --config=playwright.public-unify.config.ts
 * или: node scripts/public-unify-accept.mjs
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = join(__dirname, '../../docs/screens/public-unify')
const BASE = process.env.PUBLIC_BASE || 'http://localhost:5173'
const SLUG = process.env.STORE_SLUG || 'waysklad'

mkdirSync(OUT, { recursive: true })

const PAGES = [
  { key: 'catalog', path: `/store/${SLUG}` },
  { key: 'product', path: `/store/${SLUG}/products/1` },
  { key: 'cart', path: `/store/${SLUG}/cart` },
  { key: 'login', path: `/store/${SLUG}/login` },
  { key: 'profile', path: `/store/${SLUG}/account` },
]

const VIEWPORTS = [
  { name: '375', width: 375, height: 812 },
  { name: '1440', width: 1440, height: 900 },
]

const THEMES = ['light', 'dark']

async function setTheme(page, theme) {
  await page.evaluate((mode) => {
    const value = mode === 'dark' ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', value)
    try {
      localStorage.setItem('waysklad:theme-mode', value)
    } catch {}
  }, theme)
}

async function assertNoPlatformLexicon(page, label) {
  const text = await page.locator('body').innerText()
  const banned = ['маркетплейс', 'платформ', 'все магазины', 'Все магазины']
  const hits = banned.filter((w) => text.toLowerCase().includes(w.toLowerCase()))
  if (hits.length) {
    throw new Error(`${label}: в UI осталось: ${hits.join(', ')}`)
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext()
  const page = await context.newPage()

  // Сценарий: каталог → товар → корзина → оформление → вход → профиль → заявка
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BASE}/store/${SLUG}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await assertNoPlatformLexicon(page, 'каталог')

  const productLink = page.locator(`a[href*="/store/${SLUG}/products/"]`).first()
  if (!(await productLink.count())) throw new Error('в каталоге нет товаров')
  await productLink.click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
  await assertNoPlatformLexicon(page, 'товар')

  // мин. заказ 5 — поднимаем количество и кладём в корзину
  const qtyInput = page.getByLabel('Количество')
  if (await qtyInput.count()) {
    await qtyInput.fill('5')
  } else {
    for (let i = 0; i < 6; i++) {
      await page.getByRole('button', { name: 'Увеличить количество' }).click()
    }
  }
  const addBtn = page.getByRole('button', { name: /В корзину/i }).first()
  await addBtn.click()
  await page.waitForTimeout(500)

  await page.goto(`${BASE}/store/${SLUG}/cart`, { waitUntil: 'networkidle' })
  await assertNoPlatformLexicon(page, 'корзина')

  for (const name of ['Избранное', 'Корзина']) {
    if (!(await page.getByRole('link', { name }).first().count())) {
      throw new Error(`в шапке нет «${name}»`)
    }
  }

  // оформление без сессии → модалка входа
  await page.locator('main input').first().fill('Тест Покупатель')
  await page.waitForTimeout(200)
  await page.getByRole('button', { name: /Оформить заказ|Войти и оформить/i }).click()
  await page.waitForTimeout(800)

  await page.goto(`${BASE}/store/${SLUG}/login`, { waitUntil: 'networkidle' })
  await assertNoPlatformLexicon(page, 'вход')
  if (!(await page.getByRole('button', { name: /Войти|Зарегистрир|Продолжить|Отправить/i }).count())) {
    // форма входа/регистрации должна быть на странице
    const inputs = await page.locator('input').count()
    if (inputs < 1) throw new Error('на /login нет формы')
  }

  await page.goto(`${BASE}/store/${SLUG}/account`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  if (!page.url().includes('/login') && !page.url().includes('/account')) {
    throw new Error(`неожиданный URL профиля: ${page.url()}`)
  }

  // чат/статус заявки — страница не 500 (без токена может редиректить)
  {
    const res = await page.goto(`${BASE}/store/${SLUG}/request`, { waitUntil: 'domcontentloaded' })
    if (res && res.status() >= 500) throw new Error(`/request → ${res.status()}`)
    await page.waitForTimeout(400)
    await assertNoPlatformLexicon(page, 'заявка')
  }

  for (const path of ['/marketplace', '/cart', '/favorites', '/account']) {
    const res = await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' })
    if (res && res.status() >= 500) throw new Error(`${path} → ${res.status()}`)
    await page.waitForTimeout(300)
  }

  // «назад» с товара на каталог через логотип/крошки
  await page.goto(`${BASE}/store/${SLUG}/products/1`, { waitUntil: 'networkidle' })
  await page.getByRole('link', { name: /Каталог магазина|WaySklad/i }).first().click()
  await page.waitForURL(new RegExp(`/store/${SLUG}/?$`))
  await page.waitForTimeout(300)

  // скриншоты
  for (const theme of THEMES) {
    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      for (const p of PAGES) {
        await page.goto(`${BASE}${p.path}`, { waitUntil: 'networkidle' })
        await setTheme(page, theme)
        await page.reload({ waitUntil: 'networkidle' })
        await setTheme(page, theme)
        await page.waitForTimeout(400)
        const file = join(OUT, `${p.key}-${vp.name}-${theme}.png`)
        await page.screenshot({ path: file, fullPage: true })
        console.log('saved', file)
      }
    }
  }

  console.log('OK: сценарий и скриншоты готовы →', OUT)
  await browser.close()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
