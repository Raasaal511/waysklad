# Дизайн-система публичных страниц — шпаргалка

Публичные страницы: `/marketplace`, `/store/:slug`, `/store/:slug/products/:id`,
`/store/:slug/cart`, `/cart`, `/favorites`, страницы ошибок. Кабинет владельца
не входит.

Источник правды — блок «Д» в `docs/PUBLIC_PAGES_FINISH_PROMPTS.md` (раздел 2).
Этот файл — выжимка + таблица компонентов, чтобы следующая сессия не начала
изобретать вторую шапку или второй компонент фильтров.

## Где лежит каждый общий компонент

| Компонент | Файл | Используется на |
|---|---|---|
| `PublicHeader` | `frontend/src/widgets/public-header/PublicHeader.tsx` | все публичные страницы |
| `PublicFooter` | `frontend/src/widgets/public-header/PublicFooter.tsx` | все публичные страницы |
| `PublicLayout` | `frontend/src/widgets/public-header/PublicLayout.tsx` | обёртка шапка+контейнер+подвал |
| `ShopHeader` | `frontend/src/pages/storefront/ShopHeader.tsx` | каталог магазина, карточка товара (компактно) |
| `ProductCard` | `frontend/src/pages/storefront/ProductCard.tsx` | каталог, маркетплейс, похожие, недавние, избранное |
| `ProductGrid` | `frontend/src/pages/storefront/ProductGrid.tsx` | те же списки товаров |
| `FilterBar` | `frontend/src/pages/storefront/filters/FilterBar.tsx` | каталог магазина и маркетплейс (один компонент, разные поля) |
| `SectionHeader` | `frontend/src/shared/ui/SectionHeader.tsx` | заголовок секции + ссылка «Все ›» |
| `Chip` | `frontend/src/shared/ui/Chip.tsx` | фильтры, теги отзывов, подборки |
| `QtyStepper` (степпер количества витрины) | `frontend/src/pages/storefront/product/VariantList.tsx` (локальный компонент файла, не экспортирован — используется дважды внутри: товар без вариантов и строка варианта) | список вариантов/количество на карточке товара |
| `StarRating` | `frontend/src/shared/ui/StarRating.tsx` | везде, где рейтинг |
| `Illustration` / `EmptyState` / `ErrorState` | `frontend/src/shared/ui/EmptyState.tsx`, `ErrorState.tsx` | пустые состояния и ошибки |
| `Lightbox` | `frontend/src/shared/ui/Lightbox.tsx` | галерея товара, фото отзывов, фото покупателей |
| `Skeleton`-геометрия | у каждого компонента свой `*Skeleton` рядом (`ProductCardSkeleton`, `ShopHeaderSkeleton`, `ProductPageSkeleton`…) | состояние загрузки |
| `Money`/числа | `frontend/src/shared/lib/format.ts` (`formatMoney`, `formatQuantity`, `plural`, `formatPriceOrRequest`) | везде, где деньги/количество/склонение |
| `Breadcrumbs` | `frontend/src/shared/ui/Breadcrumbs.tsx` | каталог, карточка товара, каталог маркетплейса |

Перед тем как создавать новый компонент — искать существующий:
`grep -r "название" frontend/src`. Похожий есть → дорабатывать его, не плодить
второй.

## Цвета

Только переменные из `frontend/src/index.css`: `--bg`, `--bg-muted`, `--text`,
`--text-muted`, `--border`, `--accent`, `--accent-hover`, `--accent-soft`,
`--danger`, `--danger-bg`, `--warning`, `--warning-bg`, `--ink`, `--radius`,
`--radius-sm`. Хардкод запрещён, кроме `#fff` в кнопке на `--accent` и
`rgba(0,0,0,…)` оверлея поверх фото. Фон страницы — `--bg-muted`, карточки —
`--bg`. Светлая тема: у карточек рамки нет. Тёмная тема: рамка 1px `--border`.
Должны работать светлая/тёмная тема и все 4 `data-accent` (`green` — дефолт,
`blue`, `terracotta`, `violet`).

## Сетка и отступы

Контейнер 1280px, боковые поля 24px (≥1024) / 20px (768–1023) / 16px (<768).
Брейкпоинты: 1280, 1024, 768, 480. Вертикальный ритм между крупными блоками —
48px (≥1024) / 32px (<1024). Padding карточки — 24px (≥1024) / 16px (<768).
Шкала отступов: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 — других нет.

## Скругления

Карточка и фото — 16px; вложенные элементы и кнопки — 12px; миниатюра/бейдж —
8px; чипы и круглые кнопки — 999px.

## Типографика

- H1 страницы: 32/700/1.2 (24 на мобильном)
- Заголовок секции: 24/700/1.25 (20 на мобильном)
- Заголовок карточки-блока: 18/600/1.3
- Цена крупная: 28/700; цена в карточке товара: 18/700
- Основной текст: 16/400/1.5; вторичный: 14/400/1.45 `var(--text-muted)`
- Подпись/бейдж: 12/600, uppercase только у бейджей

Больше размеров не вводить. Заголовки — не более 2 строк (line-clamp), длинные
слова — `overflow-wrap: anywhere`.

## Кнопки

- основная: высота 48 (44 мобильный), radius 12, фон `--accent`, текст `#fff`,
  hover `--accent-hover`, active `scale(.99)`
- вторичная: тот же размер, фон `--accent-soft`, текст `--accent`
- тихая (ghost): прозрачная, текст `--text-muted`, hover фон `--bg-muted`
- иконочная: 44×44 (40 мобильный), radius 12
- круглая «+»: 32×32, фон `--accent`, иконка `#fff` 18px, stroke 2
- отключённая: `opacity .5`, `cursor: not-allowed`, без hover
- у каждой — `:focus-visible` (outline 2px `--accent`, offset 2px), не убирать

## Бейджи

На фото товара, снизу слева, колонкой, gap 4: скидка — `--danger`/`--danger-bg`;
«Новинка» — `--accent`/`--accent-soft`; «Хит» — `--warning`/`--warning-bg`;
«Нет в наличии» — `--text-muted`/`--bg-muted`, фото `opacity .6`. Не больше
двух одновременно, приоритет: нет в наличии → скидка → хит → новинка.

## Фото

Карточка товара в сетке — `aspect-ratio 1/1`, `object-fit: cover`. Главное фото
на странице товара — `aspect-ratio 4/5`, `object-fit: contain`, фон
`--bg-muted`. Миниатюра варианта — 48×48, radius 8. У всех `<img>` — заданные
размеры или `aspect-ratio` (нулевой CLS), `loading="lazy"` кроме первого
экрана, `alt` = название товара. Нет фото → `ProductPhoto`-плейсхолдер, никогда
не «битая картинка».

## Состояния

Есть у каждого блока с данными: загрузка (skeleton той же геометрии, что и
контент — это единственный надёжный способ избежать сдвига макета при
переходе skeleton → контент), пусто, ошибка, успех. Пустое/ошибка — через
`EmptyState`/`ErrorState` с иллюстрациями из `frontend/public/illustrations`
(см. `docs/ILLUSTRATIONS_PROMPTS.md`).

## Числа, деньги, склонения

- деньги: `formatMoney` + « ₽» через неразрывный пробел
- количества: `formatQuantity` — «5», не «5.000» (бэкенд отдаёт Decimal
  строкой — печатать её напрямую запрещено)
- единицы: `product.unit_label`, не хардкод «шт»
- склонения: `plural(n, ['товар','товара','товаров'])` — единая функция,
  `pluralizeGoods` удалена насовсем
- рейтинг: одна цифра после точки — «5.0»
- пустые значения не печатаем: нет отзывов — «Нет отзывов», не «0 отзывов»;
  `sold_count` 0 — бейджа нет

## Доступность

У иконочных кнопок — `aria-label`; у изображений — `alt`; модалки и лайтбокс —
фокус-ловушка, Esc, возврат фокуса; контраст текста ≥ 4.5:1 в обеих темах
(после P7 `--text-muted` и `--warning` подобраны так, чтобы проходить порог
на `--bg-muted`/`--warning-bg`); вложенных `<a>` внутри `<a>` нет (ссылка на
карточку — через `::after`). Если элемент имеет видимый текст, `aria-label`
должен включать этот текст (WCAG 2.5.3 Label in Name), а не заменять его
целиком — иначе Lighthouse ловит `label-content-name-mismatch`.

## Запреты

Новые npm-зависимости; inline-стили кроме CSS-переменных; `:global`,
`!important`, хардкод px там, где есть переменная; второй компонент того же
назначения (см. таблицу выше — сверяться перед созданием); «пока оставлю
старое рядом» — заменённый код удаляется в том же шаге.
