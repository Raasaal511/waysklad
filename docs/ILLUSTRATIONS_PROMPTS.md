# Иллюстрации, hero и onboarding: промпты для ИИ-ассистента

Задача: подключить к проекту уже готовые картинки из `frontend/public/`.
Сейчас в коде не используется ни одна из них: поиск по `src` не находит
ни `illustrations/`, ни `hero-banner`, ни `onbarding`.

---

## Что лежит в проекте (проверено 17.09.2026)

| Файл | Размер | Фон | Вес | Что изображено |
|---|---|---|---|---|
| `public/hero-banner.png` | 2243×701 | **белый, без прозрачности** | 918 КБ | Продавец за прилавком, полки, дом-крыша, коробки, растение. Зелёный + тёмно-графитовый |
| `public/onbarding.png` (опечатка в имени) | 1568×1003 | **белый, без прозрачности** | 1,05 МБ | Продавец показывает телефон с приложением, рядом магазин с полосатым навесом |
| `illustrations/empty-box.png` | 495×457 | прозрачный | 211 КБ | Пустая коробка |
| `illustrations/empty-shelf.png` | 411×487 | прозрачный | 156 КБ | Пустая полка |
| `illustrations/empty-cart.png` | 496×398 | прозрачный | 171 КБ | Пустая корзина |
| `illustrations/empty-archive.png` | 397×387 | прозрачный | 122 КБ | Пустой архивный ящик |
| `illustrations/error-404-not-found.png` | 442×427 | прозрачный | 198 КБ | Магазин со знаком вопроса |
| `illustrations/error-403-blocked.png` | 449×419 | прозрачный | 190 КБ | Магазин с замком |
| `illustrations/state-telegram-confirm.png` | 538×462 | прозрачный | 220 КБ | Телефон с Telegram и человек |

### Проблемы, которые нужно решить

1. **У hero и onboarding белый фон.** На фоне `--bg-muted` и в тёмной теме
   будет виден белый прямоугольник. Фон нужно вырезать. Внутри картинок
   есть белые детали, которые должны остаться: экран телефона, белые
   полосы навеса, витрина. Поэтому глобальная замена белого на прозрачный
   не подходит, нужна заливка от краёв.
2. **Вес.** Иллюстрации показываются в размере 120–200 px, а весят по
   200 КБ. Hero и onboarding весят около 1 МБ. Нужны WebP в размерах 1x и 2x.
3. **Тёмная тема.** В рисунках много тёмно-графитового цвета (#263238),
   и на фоне `#1a1d21` силуэты сольются. Нужна светлая подложка.
4. **Цвет акцента.** Рисунки зелёные, а у владельца может быть выбран
   синий, терракотовый или фиолетовый акцент. Перекрашивать через
   `hue-rotate` нельзя: вместе с зелёным поменяется цвет лица персонажа.
   Оставляем иллюстрации фирменно-зелёными: это арт бренда, а не элементы
   интерфейса.
5. **Бонус: в манифесте PWA есть ссылки на `pwa-192.png` и
   `pwa-512.png`, но самих файлов в `public/` нет.** Иконки установки
   приложения сейчас отдают 404.

---

## Где какая картинка (карта размещения)

| Картинка | Экран и состояние | Размер |
|---|---|---|
| **hero-banner** | Главная маркетплейса: первый слайд-заглушка, если баннеров из API нет (см. `MARKETPLACE_HOME_PROMPTS.md`) | во всю ширину, 280px |
| hero-banner (мобильный кроп) | Тот же слайд на телефоне | 16:10 |
| **onboarding** | 1) Приветственное окно перед туром (`OnboardingOverlay`) 2) Левая панель страницы входа и регистрации на десктопе 3) Промо-плитка «Продавайте на ВайСклад» на главной маркетплейса | 320–520px |
| **empty-box** | Товары: товаров пока нет · Витрина: пока нет товаров · Отзывы: пока нет · Задачи: активных нет | 160px |
| **empty-shelf** | Склады: складов пока нет · Склад: остатков пока нет · Маркетплейс: пока нет магазинов | 160px |
| **empty-cart** | Корзина витрины пуста · Продажи: продаж пока нет · Заказы: активных нет | 160px |
| **empty-archive** | Завершённые заказы и задачи · Погашенные долги · История движений · Мои заявки покупателя · Клиент: покупок и событий нет · Админка: ошибок нет | 140px |
| **error-404** | Витрина не найдена · Товар не найден · Заявка не найдена · Внутренние «… не найден» (товар, продажа, заказ, склад, долг, клиент) · **новая** страница 404 для неизвестных адресов | 200px |
| **error-403** | Магазин заблокирован (403 на витрине, в карточке товара и в корзине) | 200px |
| **state-telegram-confirm** | Вход покупателя: шаг «Ожидаем подтверждение…» · Профиль владельца: подключение Telegram-бота | 180px |

«Ничего не найдено» при поиске и фильтрах показывается **без большой
иллюстрации**: только текст и кнопка «Сбросить фильтры». Большая картинка
при каждом пустом поиске утомляет.

---

## Промпт I1 — подготовка файлов

```text
Проект ВайСклад, фронтенд: frontend/ (React 19 + Vite + vite-plugin-pwa).
Задача — подготовить графику в frontend/public/. Код приложения на этом
шаге НЕ трогаем, кроме vite.config.ts (пункт 6).

Инструменты: Python 3 + Pillow (если нет — pip install pillow). Для WebP
подойдёт Pillow или cwebp, если он установлен. Скрипт положи в
frontend/scripts/build_images.py, чтобы шаг можно было повторить.
Исходники не удаляй, а перенеси в frontend/design-src/ — эта папка не
попадает в сборку.

1. ВЫРЕЗАТЬ БЕЛЫЙ ФОН у public/hero-banner.png и public/onbarding.png.
   - Фон почти белый, не строго #FFFFFF: порог — все каналы ≥ 238.
   - Делай заливку (flood fill) от ВСЕХ пикселей по краям картинки:
     прозрачными становятся только светлые пиксели, связанные с краем.
     Белые области внутри рисунка (экран телефона, витрина, полосы
     навеса в onboarding) должны остаться белыми и непрозрачными.
   - Сглаживание края: для пикселей на границе залитой области alpha
     считай по расстоянию до белого (светлее — прозрачнее), без жёсткой
     лесенки. Убери белый ореол (defringe): у полупрозрачных пикселей
     восстанови цвет, вычтя вклад белого.
   - ПРОВЕРКА onboarding: белые полосы навеса внизу касаются фона
     и могут «утечь». Если после заливки полосы стали прозрачными —
     защити прямоугольную область навеса (примерно x 940–1510,
     y 320–500 в исходных координатах 1568×1003; уточни по картинке)
     от заливки и повтори.
   - Обрежь пустые прозрачные поля (оставь отступ 16px).
   - Сохрани результат как PNG с альфой в design-src/ (мастер-копии)
     и покажи мне превью каждого результата на трёх подложках: белой,
     #f1f3f5 и #1a1d21. Склей их в один PNG
     (design-src/_preview.png), чтобы я мог проверить глазами.

2. ПЕРЕИМЕНОВАТЬ и РАЗЛОЖИТЬ:
   public/illustrations/hero-market.webp        (из hero-banner)
   public/illustrations/hero-market-mobile.webp (кроп, см. п.3)
   public/illustrations/onboarding.webp         (из onbarding — исправить опечатку)
   Остальные 7 файлов — в той же папке, те же имена, но .webp.

3. МОБИЛЬНЫЙ КРОП hero: из очищенного hero вырежи центральную часть с
   продавцом, прилавком и ближайшими полками, пропорция 16:10. Персонаж
   не должен касаться края кадра.

4. РАЗМЕРЫ (WebP с альфой, quality 82, method 6):
   - hero-market: ширина 1200 и 2400 (или максимум исходника) → суффиксы
     @1x и @2x: hero-market@1x.webp, hero-market@2x.webp
   - hero-market-mobile: 640 и 1280
   - onboarding: 520 и 1040
   - 7 маленьких иллюстраций: 200 и 400 (по ширине)
   Итоговый вес: маленькие ≤ 25 КБ за @1x, hero ≤ 180 КБ за @2x.
   Если не укладывается — снизь quality до 75 и сообщи.

5. PWA-ИКОНКИ (в манифесте есть ссылки, файлов нет):
   из public/logo.png (1254×1254) сделай
   public/pwa-192.png, public/pwa-512.png и
   public/pwa-512-maskable.png (логотип на фоне #1b6b4d, отступ 20%
   под safe zone), public/apple-touch-icon.png (180×180, без прозрачности,
   фон белый).
   OG-картинка по умолчанию: public/og-default.png 1200×630 — очищенный
   hero на фоне #e8f0ea, логотип-знак слева сверху и надпись
   «ВайСклад — магазины вашего города» (шрифт возьми системный sans,
   если нужного нет — сообщи). Надпись рисуй тёмным #14251c.

6. vite.config.ts:
   - в manifest.icons добавь maskable-иконку (purpose: 'maskable')
   - в VitePWA добавь includeAssets: ['favicon.svg', 'apple-touch-icon.png']
   - workbox.globPatterns: стандартные + 'illustrations/*@1x.webp'
     (маленькие иллюстрации должны работать офлайн; hero и @2x
     в precache НЕ класть)
   index.html: <link rel="apple-touch-icon" href="/apple-touch-icon.png">,
   <meta property="og:image" content="/og-default.png">,
   <meta name="description" content="Товарный учёт и витрина для малого бизнеса">.

7. Обнови frontend/api_docs/wikkeo_design_reference.md, раздел «Готовые
   иллюстрации»: новые имена и пути, размеры, пометка, что фон hero и
   onboarding вырезан, и где лежат исходники.

8. npm run build — без ошибок. В dist/ проверь, что есть все новые файлы
   и sw.js содержит illustrations/*@1x.webp, но не hero.

Отчёт: таблица «файл → размеры → вес», ссылка на _preview.png, что
пришлось поправить вручную.
```

---

## Промпт I2 — компонент Illustration и пустые состояния

```text
Шаг I2. Файлы из I1 уже лежат в public/illustrations/ (проверь).
Стек: React 19, CSS Modules, переменные из src/index.css. Новые
библиотеки не добавлять.

1. shared/ui/Illustration.tsx:
   props: name: 'empty-box' | 'empty-shelf' | 'empty-cart' | 'empty-archive'
          | 'error-404-not-found' | 'error-403-blocked'
          | 'state-telegram-confirm' | 'onboarding';
          size?: number (ширина в px, по умолчанию 160);
          alt?: string (по умолчанию "" и aria-hidden, картинка декоративная)
   Рендер: <img src=/illustrations/<name>@1x.webp
                srcSet="…@1x.webp 1x, …@2x.webp 2x"
                width, height (по пропорции исходника — вынеси размеры в
                константу, чтобы не было прыжков вёрстки),
                loading="lazy" decoding="async">
   Обёртка .plate:
     - светлая тема: без фона
     - тёмная тема (:root[data-theme='dark']): круглая светлая подложка
       background: color-mix(in srgb, #ffffff 90%, var(--accent) 10%);
       border-radius: 50%; padding: 14%; — чтобы тёмные силуэты не сливались
       с фоном. Для onboarding — radius 24px вместо круга.
   Появление: fade + translateY(6px) за 240ms, отключается при
   prefers-reduced-motion.

2. shared/ui/EmptyState.tsx:
   props: illustration?: Illustration name; title: string;
          description?: string; action?: ReactNode; compact?: boolean
   Вёрстка: колонка по центру, иллюстрация, заголовок 18px/600,
   описание 14px var(--text-muted) (max-width 360px), действие.
   compact — иллюстрация 96px, отступы меньше (для вкладок внутри карточек).
   Без illustration — просто текст (для «Ничего не найдено»).

3. Замени текущие текстовые пустые состояния на EmptyState. Найди все места
   через grep "пока нет|Пока нет|не найден|Ничего не найдено|нет$".
   Минимальный список:
   - ProductsPage: «Товаров пока нет» (сейчас есть только «Товаров не
     найдено» — раздели состояния: база пуста / фильтр ничего не нашёл),
     empty-box, действие «Добавить товар» → /products/new
   - StockPage «Складов пока нет» → empty-shelf, «Создать склад»
   - WarehouseDetailPage «На этом складе остатков пока нет» → empty-shelf,
     «Принять товар»
   - SalePage «Продаж пока нет — начните первую» → empty-cart,
     «Новая продажа»
   - OrdersPage активные → empty-cart; завершённые → empty-archive
   - TasksPage активные → empty-box; завершённые → empty-archive
   - DebtsPage «Погашенных долгов нет» → empty-archive
   - MovementHistoryPage «Движений товара пока не было» → empty-archive
   - ClientDetailPage «Покупок/Событий/Долгов пока нет» → compact,
     empty-archive
   - AdminPage «Пока нет записанных ошибок» → compact, empty-archive
   - StorefrontCatalogPage «Пока нет товаров» → empty-shelf
   - StorefrontCartPage пустая корзина → empty-cart, «В каталог»
   - StorefrontMyOrdersPage «Пока нет заявок» → empty-archive,
     «Перейти к покупкам»
   - MarketplacePage «Пока нет магазинов с открытой витриной» →
     empty-shelf
   - все «Ничего не найдено» → EmptyState без картинки + кнопка
     «Сбросить фильтры» (ResetFiltersButton, если подходит)
   - ClientsPage «Клиентов/Поставщиков пока нет»: подходящей картинки
     нет → текстовый EmptyState с действием «Добавить клиента». Добавь
     этот экран в список недостающих картинок (см. I5).
   Тексты заголовков оставь как есть, добавь короткие описания
   («Добавьте первый товар — он появится здесь и на витрине»).

Проверка: скриншоты 375 и 1440, светлая и тёмная тема, для 5 любых
экранов из списка. build и lint чистые. В отчёте — таблица «экран →
картинка».
```

---

## Промпт I3 — страницы ошибок 404 и 403

```text
Шаг I3. Используй EmptyState и Illustration из I2.

1. shared/ui/ErrorState.tsx: kind: 'not-found' | 'blocked' | 'network';
   title и description необязательны (есть тексты по умолчанию);
   onRetry?; backTo?: { to: string; label: string }.
   - not-found → error-404-not-found, «Страница не найдена»
   - blocked → error-403-blocked, «Магазин временно недоступен»,
     «Магазин приостановлен платформой. Попробуйте зайти позже»
   - network → без картинки (иконка IconWifiOff 48px), «Нет связи с
     сервером», кнопка «Повторить»

2. Новая страница pages/NotFoundPage.tsx и роут path="*" в App.tsx
   (последним, вне RequireAuth): ErrorState not-found и две кнопки —
   «На главную» (/marketplace) и «Войти в кабинет» (/login).

3. Витрина: StorefrontCatalogPage, StorefrontProductPage,
   StorefrontCartPage, StorefrontRequestPage — различай статусы ApiError:
   404 → not-found («Витрина не найдена или выключена» / «Товар не
   найден или скрыт магазином» / «Заявка не найдена»),
   403 → blocked, остальные → network с повтором.
   Проверь в backend/app/presentation/storefront/router.py, какой статус
   реально приходит для заблокированного магазина (is_suspended). Если
   там 404, а не 403, — ничего не придумывай, напиши об этом в отчёте.

4. Внутренние детальные страницы (ProductDetailPage, ProductEditPage,
   SaleDetailPage, OrderDetailPage, WarehouseDetailPage,
   WarehouseMovementPage, DebtDetailPage, ClientDetailPage): вместо
   красного текста «… не найден» — ErrorState not-found с кнопкой
   «Назад к списку». Сетевые ошибки — network с повтором.

Проверка: /abracadabra, /store/net-takogo, /store/<slug>/products/999999,
отключённый бэкенд (network). Скриншоты 375 и 1440.
```

---

## Промпт I4 — страница входа с иллюстрацией

```text
Шаг I4: страница входа и регистрации (pages/auth/LoginPage.tsx +
LoginPage.module.css). Логику форм НЕ трогать.

1. ≥ 960px — две колонки: слева панель 44% ширины, справа текущая
   карточка формы по центру.
   Левая панель: фон var(--accent-soft), скругление 28px, внутренний
   отступ 48px, содержимое по вертикали:
   - логотип-знак и «WaySklad»
   - заголовок 32px/700: «Учёт, продажи и витрина — в одном телефоне»
   - Illustration name="onboarding" size 440 (в тёмной теме — подложка
     из I2)
   - три пункта с иконками @tabler (IconCheck в круге var(--accent)):
     «Остатки и продажи без Excel»,
     «Долги и рассрочка клиентов под контролем»,
     «Своя витрина: покупатели заказывают онлайн»
   - внизу мелко: «Бесплатно. Без карты. Настройка за 5 минут»
   На вкладке «Регистрация» заголовок меняется на «Откройте свой магазин
   за 5 минут» (плавная смена текста, fade 200ms).
2. < 960px — панели нет, форма как сейчас. Над формой вместо панели —
   узкая полоска с иллюстрацией 120px только на вкладке «Регистрация».
3. Ссылка под формой «Я покупатель — перейти к магазинам →» ведёт
   на /marketplace.

Проверка: 375, 960, 1440, светлая и тёмная тема; переключение вкладок
не дёргает вёрстку (размеры картинки заданы заранее).
```

---

## Промпт I5 — onboarding, Telegram и недостающие иллюстрации

```text
Шаг I5.

1. ПРИВЕТСТВЕННЫЙ ЭКРАН ПЕРЕД ТУРОМ (app/OnboardingOverlay.tsx +
   OnboardingContext.tsx). Сейчас тур сразу начинается шагом
   «Быстро настроим магазин: начнём со склада».
   Добавь нулевой шаг id: 'welcome' без target. Это модалка по центру
   (не карточка-подсказка), ширина 520px, на мобильном — нижний шит:
   - Illustration name="onboarding" size 360
   - «Добро пожаловать в ВайСклад, <имя владельца>!»
   - «Покажем главное за 2 минуты: склад → товар → первая продажа →
     продавец → выручка»
   - индикатор шагов (6 точек)
   - кнопки «Начать» (primary) и «Позже» (ghost). «Позже» = текущий skip.
   Остальные шаги не меняй. Логику «пройден» (localStorage
   waysklad:onboarding-done:<userId>) не ломай.
   Esc работает как «Позже». Фокус при открытии — на «Начать».

2. TELEGRAM (pages/storefront/CustomerLoginModal.tsx): на шаге ожидания
   («Ожидаем подтверждение…») покажи Illustration
   name="state-telegram-confirm" size 180 над текстом и мягкую пульсацию
   точки рядом со словом «Ожидаем». Тот же приём — в профиле владельца,
   в блоке подключения Telegram-бота (ищи connectTelegram), пока
   подключение не завершено.

3. СПИСОК НЕДОСТАЮЩИХ КАРТИНОК: создай frontend/api_docs/illustrations_todo.md
   с таблицей «экран → что нужно нарисовать → имя файла → где в коде
   сейчас текстовая заглушка». Минимум: клиенты (empty-clients),
   долги — активных нет, это хорошая новость (state-no-debts),
   аналитика — мало данных (empty-analytics), сотрудники
   (empty-employees), уведомления (empty-notifications), офлайн
   (state-offline), успешная заявка (state-request-sent), категории
   маркетплейса (8 штук, см. MARKETPLACE_HOME_PROMPTS.md).
   Код для них не пиши — только список.
```

---

## Промпт I6 — генерация недостающих картинок (для генератора изображений, не для кодового ассистента)

Общий стиль, который нужно добавлять к каждому запросу:

```text
Flat vector illustration, minimal geometric shapes, no outlines, no gradients,
no text, no letters. Palette strictly: green #3DA35D, light green #7CC68F,
dark slate #263238, skin tone #F2A56B, white #FFFFFF. Same style as a friendly
shop-keeper character in a green cap and green apron. Centered single object,
generous empty space around it, transparent background (PNG with alpha),
1024x1024.
```

Сами объекты (добавить в начало запроса):

- `empty-clients`: «Two simple empty chairs next to a small round table with an empty notebook»
- `state-no-debts`: «An open notebook with a big green check mark and a closed padlock-free wallet, celebratory small sparkles»
- `empty-analytics`: «A simple bar chart board with only one tiny bar and a small magnifying glass»
- `empty-employees`: «An empty green apron hanging on a hook with a name badge without text»
- `empty-notifications`: «A quiet bell with a small 'z' sleep symbol made of shapes, not letters»
- `state-offline`: «A small shop building with a cloud and a crossed wifi symbol above it»
- `state-request-sent`: «A paper bag with a green check mark and a flying paper plane»
- категории маркетплейса, по одной на картинку: «Headphones», «Folded hoodie», «Sneaker», «Cordless drill», «Car tire», «Handbag», «Grocery bag with vegetables», «Kitchen pot and pan» — стиль тот же, объект в правом нижнем углу кадра 4:3

После генерации прогоните каждую картинку через скрипт из I1:
`frontend/scripts/build_images.py`. Он проверит прозрачность, обрежет поля
и сделает WebP.
