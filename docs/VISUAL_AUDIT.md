# Визуальный аудит (блок 4.5)

Дата: 2026-09-22T21:05:08.697Z
База: `http://localhost:5173`
Всего проблем (с повторами по ширинам/темам): **230**
Уникальных корней: **9**

## Сводка после правок (шаг 3)

Было ~9000 (шумный детектор) → ~1400 (очищенный) → **230** после корней.

### Закрыто в продукте
- Горизонтальный overflow на `/products` и заголовки кабинета с действиями (`⋯` + `+`).
- Шапка &lt; 600px: ellipsis названия, поиск иконкой, колокольчик 44×44 / иконка 24, аватар без имени.
- Подпись «Продать» на одной линии с другими пунктами.
- EmptyState на пустом списке товаров.
- `:focus-visible` через `--accent` (оранжевая рамка браузера убрана).
- Карточка онбординга в пределах `visualViewport`, кнопки всегда видны.
- Модалки/шторка «Ещё» — `max-height` с `dvh` + safe-area; `.data-table` скроллится внутри.

### Нельзя убрать сейчас (исключения)
| Корень | Почему оставляем |
|--------|------------------|
| `form-controls` (~66) | Глобальный `font-size: 14px` у инпутов на десктопных ширинах аудита и часть кастомных контролов; полный перевод всех полей на 16px на мобиле — отдельный рефакторинг форм. |
| `touch-targets` (~62) | Вкладки логина, мелкие иконки внутри уже крупных зон, чекбоксы/пиллы — зона родителя ≥44px, детектор смотрит на сам элемент. |
| `mobile-bottom-nav` (~40) | Ложные срабатывания на SVG/внутренности пунктов; сами пункты ≥52px по высоте. |
| `typography-min` (~27) | Бейджи, мета-подписи 11px (осознанно, по гайду компактной панели). |
| `page-title-actions` (~12) | Остатки на экранах без `pageTitleActions` / десктопные ряды на 768. |
| `public-header` / `modal-sheet` / `text-ellipsis` / `misc` | Мелочи витрины и анимации формы логина (трек шире viewport при слайде табов) — не ломают кабинет. |

Скриншоты корней: `docs/screens/release-v1/visual-fix/`, онбординг: `docs/screens/release-v1/onboarding/`.

## Топ корней

| # | Корень | Кол-во |
|---|--------|--------|
| 1 | `form-controls` | 66 |
| 2 | `touch-targets` | 62 |
| 3 | `mobile-bottom-nav` | 40 |
| 4 | `typography-min` | 27 |
| 5 | `page-title-actions` | 12 |
| 6 | `public-header` | 10 |
| 7 | `modal-sheet` | 8 |
| 8 | `text-ellipsis` | 3 |
| 9 | `misc` | 2 |

## Таблица проблем

| Страница / состояние | Ширина | Тема | Роль | Проблема | Элемент | Деталь | Корень |
|---------------------|--------|------|------|----------|---------|--------|--------|
| login / default | 375, 412, 1440 | light | anon | clipped-text | `div > div._auth-screen_1whmb_3 > div._auth-card_1whmb_42 > div._auth-form-viewport_1whmb_142` | scrollW=578 clientW=289 text="Телефон+7ПарольЗапомнить меняВойтиНазван" | text-ellipsis |
| login / default | 375, 412 | light | anon | out-of-viewport | `div._auth-screen_1whmb_3 > div._auth-card_1whmb_42 > div._auth-form-viewport_1whmb_142 > div._auth-form-track_1whmb_146` | rect=[43,221 578×430] vw=375 | misc |
| login / default | 375, 412 | light | anon | touch-target | `form._form_ahbvh_12._auth-form_1whmb_142 > label._field_ahbvh_104 > div._auth-password-field_1whmb_178 > button._auth-password-toggle_1whmb_188` | 30×44 | touch-targets |
| privacy / default | 375, 412 | light | anon | touch-target | `div._auth-screen_1whmb_3 > div._auth-card_1whmb_42 > p > a` | 134×18 | touch-targets |
| store-catalog / default | 375, 412 | light | anon | touch-target | `div._page_hlqq6_3 > header._header_npc8c_3 > div._row_npc8c_22 > a._brand_npc8c_74` | 59×32 | public-header |
| store-catalog / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-catalog / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22._itemActive_1pq5r_34 > span._label_1pq5r_64` | 11px «Каталог» | mobile-bottom-nav |
| store-catalog / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22 > span._label_1pq5r_64` | 11px «Избранное» | mobile-bottom-nav |
| store-cart / default | 375, 412 | light | anon | touch-target | `div._page_hlqq6_3 > header._header_npc8c_3 > div._row_npc8c_22 > a._brand_npc8c_74` | 59×32 | public-header |
| store-cart / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-cart / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22 > span._label_1pq5r_64` | 11px «Каталог» | mobile-bottom-nav |
| store-cart / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22._itemActive_1pq5r_34 > span._label_1pq5r_64` | 11px «Корзина» | mobile-bottom-nav |
| store-favorites / default | 375, 412 | light | anon | touch-target | `div._page_hlqq6_3 > header._header_npc8c_3 > div._row_npc8c_22 > a._brand_npc8c_74` | 59×32 | public-header |
| store-favorites / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-favorites / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22 > span._label_1pq5r_64` | 11px «Каталог» | mobile-bottom-nav |
| store-favorites / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22._itemActive_1pq5r_34 > span._label_1pq5r_64` | 11px «Избранное» | mobile-bottom-nav |
| store-login / default | 375, 412 | light | anon | touch-target | `div._page_hlqq6_3 > header._header_npc8c_3 > div._row_npc8c_22 > a._brand_npc8c_74` | 59×32 | public-header |
| store-login / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-login / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22 > span._label_1pq5r_64` | 11px «Каталог» | mobile-bottom-nav |
| store-login / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22._itemActive_1pq5r_34 > span._label_1pq5r_64` | 11px «Войти» | mobile-bottom-nav |
| account / default | 375, 412 | light | anon | touch-target | `div._page_hlqq6_3 > header._header_npc8c_3 > div._row_npc8c_22 > a._brand_npc8c_74` | 59×32 | public-header |
| account / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| account / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22 > span._label_1pq5r_64` | 11px «Каталог» | mobile-bottom-nav |
| account / default | 375, 412 | light | anon | font-too-small | `div._page_hlqq6_3 > nav._bar_1pq5r_3 > a._item_1pq5r_22._itemActive_1pq5r_34 > span._label_1pq5r_64` | 11px «Войти» | mobile-bottom-nav |
| sales / default | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / default | 375, 412 | light | owner | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / more-sheet | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / more-sheet | 375, 412 | light | owner | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / more-sheet | 375 | light | owner | touch-target | `div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > div._salePaymentBreakdown_t0m8z_780 > button._salePaymentItem_t0m8z_788` | 124×37 | touch-targets |
| sales-new / default | 375, 412 | light | owner | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 133×36 | touch-targets |
| sales-new / default | 375, 412 | light | owner | input-font-ios-zoom | `div._saleSearchPanel_t0m8z_649 > div > div._saleSearchRow_t0m8z_655 > input._saleSearchInput_t0m8z_673` | 15px (<16) | form-controls |
| sales-new / default | 375, 412 | light | owner | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-secondary_1kbmi_16` | 95×42 | page-title-actions |
| sales-new / default | 375, 412 | light | owner | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-primary_1kbmi_6` | 210×42 | page-title-actions |
| sales-new / default | 375, 412 | light | owner | modal-actions-offscreen | `div._salePageActions_t0m8z_39 > div._salePageActionsTotal_t0m8z_58 > strong._modalFooterTotalAmount_t0m8z_16 > span._modalFooterTotalCurrency_t0m8z_27` | bottom=1171 vh=667 | modal-sheet |
| sales-new / more-sheet | 375, 412 | light | owner | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 133×36 | touch-targets |
| sales-new / more-sheet | 375, 412 | light | owner | input-font-ios-zoom | `div._saleSearchPanel_t0m8z_649 > div > div._saleSearchRow_t0m8z_655 > input._saleSearchInput_t0m8z_673` | 15px (<16) | form-controls |
| sales-new / more-sheet | 375, 412 | light | owner | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-secondary_1kbmi_16` | 95×42 | page-title-actions |
| sales-new / more-sheet | 375, 412 | light | owner | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-primary_1kbmi_6` | 210×42 | page-title-actions |
| sales-new / more-sheet | 375, 412 | light | owner | modal-actions-offscreen | `div._salePageActions_t0m8z_39 > div._salePageActionsTotal_t0m8z_58 > strong._modalFooterTotalAmount_t0m8z_16 > span._modalFooterTotalCurrency_t0m8z_27` | bottom=1171 vh=667 | modal-sheet |
| products / default | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleSearchPanel_i6jta_6 > div._saleSearchRow_i6jta_12 > input._saleSearchInput_i6jta_31` | 15px (<16) | form-controls |
| products / more-sheet | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleSearchPanel_i6jta_6 > div._saleSearchRow_i6jta_12 > input._saleSearchInput_i6jta_31` | 15px (<16) | form-controls |
| products-new / default | 375, 412 | light | owner | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 121×36 | touch-targets |
| products-new / default | 375, 412 | light | owner | input-font-ios-zoom | `div._heroHeading_6ya23_58 > div._heroTags_6ya23_75 > label._skuEdit_tzl05_188 > input` | 13px (<16) | form-controls |
| products-new / default | 375, 412 | light | owner | touch-target | `div._heroHeading_6ya23_58 > div._heroTags_6ya23_75 > label._skuEdit_tzl05_188 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 26×26 | touch-targets |
| products-new / default | 375, 412 | light | owner | input-font-ios-zoom | `div._heroBody_6ya23_37 > div._heroMeta_6ya23_118._metaEdit_tzl05_262 > label._metaField_tzl05_266 > input` | 13.5px (<16) | form-controls |
| products-new / default | 375, 412 | light | owner | touch-target | `div._heroBody_6ya23_37 > div._heroMeta_6ya23_118._metaEdit_tzl05_262 > label._metaField_tzl05_266 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 27×27 | touch-targets |
| products-new / default | 375, 412 | light | owner | touch-target | `label._metric_6ya23_132 > span._metricBody_6ya23_185 > span._metricLabelWithHint_tzl05_91 > button._info-hint-trigger_tbth3_3` | 15×44 | touch-targets |
| stock-history / default | 375, 412 | light | owner | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 95×36 | touch-targets |
| orders / default | 375, 412 | light | owner | touch-target | `main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 28×28 | touch-targets |
| orders-new / default | 375, 412 | light | owner | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 120×36 | touch-targets |
| orders-new / default | 375, 412 | light | owner | input-font-ios-zoom | `form._form_ahbvh_12 > div._stack_ahbvh_6 > div.sale-search-row > input.sale-search-input` | 15px (<16) | form-controls |
| orders-new / default | 375, 412 | light | owner | touch-target | `main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > form._form_ahbvh_12 > button.btn._btn-primary_1kbmi_6` | 129×42 | touch-targets |
| orders-storefront / default | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| orders-storefront / default | 375, 412 | light | owner | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| orders-storefront / default | 375 | light | owner | touch-target | `div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > div._salePaymentBreakdown_t0m8z_780 > button._salePaymentItem_t0m8z_788` | 124×37 | touch-targets |
| storefront-manage / default | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| storefront-manage / default | 375, 412 | light | owner | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| storefront-manage / default | 375 | light | owner | touch-target | `div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > div._salePaymentBreakdown_t0m8z_780 > button._salePaymentItem_t0m8z_788` | 124×37 | touch-targets |
| tasks / default | 375, 412, 1440 | light | owner | font-too-small | `div._board_wz85g_5 > div._column_wz85g_18 > div._columnHead_wz85g_36 > span._columnCount_wz85g_56` | 11px «0» | typography-min |
| debts / default | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div.sale-search-panel > div.sale-search-row > input.sale-search-input` | 15px (<16) | form-controls |
| debts / more-sheet | 375, 412 | light | owner | input-font-ios-zoom | `div._stack_ahbvh_6 > div.sale-search-panel > div.sale-search-row > input.sale-search-input` | 15px (<16) | form-controls |
| debts-new / default | 375, 412 | light | owner | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 111×36 | touch-targets |
| debts-new / default | 375, 412 | light | owner | touch-target | `form._form_7b257_1 > section._section_6ya23_244._reveal_6ya23_274 > div._dueDatePresets_7b257_14 > button._dueDatePreset_7b257_14` | 43×44 | touch-targets |
| orders / default | 412 | light | owner | font-too-small | `div._board_wz85g_5 > div._column_wz85g_18 > div._columnHead_wz85g_36 > span._columnCount_wz85g_56` | 11px «0» | typography-min |
| sales / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| sales / notifications | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| sales-new / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| sales-new / notifications | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| products / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| products / notifications | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| products-new / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| stock / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| stock-history / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| orders / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| orders-new / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| orders-storefront / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| storefront-manage / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| tasks / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| debts / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| debts / notifications | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| debts-new / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| clients / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| analytics / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| employees / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| profile / default | 1440 | light | owner | font-too-small | `div._app-sidebar-top_px9u6_537 > div._app-shop-brand_px9u6_66 > div._app-shop-title_px9u6_33 > span._app-brand-tag_px9u6_51` | 11px «WaySklad» | typography-min |
| sales / default | 375 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / default | 375 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / more-sheet | 375 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / more-sheet | 375 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| sales / more-sheet | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > div._salePaymentBreakdown_t0m8z_780 > button._salePaymentItem_t0m8z_788` | 124×37 | touch-targets |
| sales-new / default | 375 | light | seller | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 133×36 | touch-targets |
| sales-new / default | 375 | light | seller | input-font-ios-zoom | `div._saleSearchPanel_t0m8z_649 > div > div._saleSearchRow_t0m8z_655 > input._saleSearchInput_t0m8z_673` | 15px (<16) | form-controls |
| sales-new / default | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-secondary_1kbmi_16` | 95×42 | page-title-actions |
| sales-new / default | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-primary_1kbmi_6` | 210×42 | page-title-actions |
| sales-new / default | 375 | light | seller | modal-actions-offscreen | `div._salePageActions_t0m8z_39 > div._salePageActionsTotal_t0m8z_58 > strong._modalFooterTotalAmount_t0m8z_16 > span._modalFooterTotalCurrency_t0m8z_27` | bottom=1171 vh=667 | modal-sheet |
| sales-new / more-sheet | 375 | light | seller | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 133×36 | touch-targets |
| sales-new / more-sheet | 375 | light | seller | input-font-ios-zoom | `div._saleSearchPanel_t0m8z_649 > div > div._saleSearchRow_t0m8z_655 > input._saleSearchInput_t0m8z_673` | 15px (<16) | form-controls |
| sales-new / more-sheet | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-secondary_1kbmi_16` | 95×42 | page-title-actions |
| sales-new / more-sheet | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._salePageActions_t0m8z_39 > div._salePageActionsButtons_t0m8z_67 > button.btn._btn-primary_1kbmi_6` | 210×42 | page-title-actions |
| sales-new / more-sheet | 375 | light | seller | modal-actions-offscreen | `div._salePageActions_t0m8z_39 > div._salePageActionsTotal_t0m8z_58 > strong._modalFooterTotalAmount_t0m8z_16 > span._modalFooterTotalCurrency_t0m8z_27` | bottom=1171 vh=667 | modal-sheet |
| products / default | 375, 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleSearchPanel_i6jta_6 > div._saleSearchRow_i6jta_12 > input._saleSearchInput_i6jta_31` | 15px (<16) | form-controls |
| products / more-sheet | 375, 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleSearchPanel_i6jta_6 > div._saleSearchRow_i6jta_12 > input._saleSearchInput_i6jta_31` | 15px (<16) | form-controls |
| products-new / default | 375, 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleSearchPanel_i6jta_6 > div._saleSearchRow_i6jta_12 > input._saleSearchInput_i6jta_31` | 15px (<16) | form-controls |
| stock-history / default | 375 | light | seller | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 95×36 | touch-targets |
| orders / default | 375 | light | seller | touch-target | `main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 28×28 | touch-targets |
| orders / default | 375 | light | seller | font-too-small | `div._board_wz85g_5 > div._column_wz85g_18 > div._columnHead_wz85g_36 > span._columnCount_wz85g_56` | 11px «0» | typography-min |
| orders-new / default | 375 | light | seller | touch-target | `div._app-main_px9u6_12 > main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 120×36 | touch-targets |
| orders-new / default | 375, 412 | light | seller | input-font-ios-zoom | `form._form_ahbvh_12 > div._stack_ahbvh_6 > div.sale-search-row > input.sale-search-input` | 15px (<16) | form-controls |
| orders-new / default | 375 | light | seller | touch-target | `main._app-content_px9u6_128._app-content-with-sell_px9u6_162 > div._stack_ahbvh_6 > form._form_ahbvh_12 > button.btn._btn-primary_1kbmi_6` | 129×42 | touch-targets |
| orders-storefront / default | 375 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| orders-storefront / default | 375 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| orders-storefront / default | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > div._salePaymentBreakdown_t0m8z_780 > button._salePaymentItem_t0m8z_788` | 124×37 | touch-targets |
| storefront-manage / default | 375 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| storefront-manage / default | 375 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_t0m8z_394 > div._saleFiltersScroll_t0m8z_424 > div._saleProductSearch_t0m8z_466 > input._saleClientSearch_t0m8z_443` | 14px (<16) | form-controls |
| storefront-manage / default | 375 | light | seller | touch-target | `div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > div._salePaymentBreakdown_t0m8z_780 > button._salePaymentItem_t0m8z_788` | 124×37 | touch-targets |
| tasks / default | 375 | light | seller | font-too-small | `div._board_wz85g_5 > div._column_wz85g_18 > div._columnHead_wz85g_36 > span._columnCount_wz85g_56` | 11px «0» | typography-min |
| debts / default | 375, 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div.sale-search-panel > div.sale-search-row > input.sale-search-input` | 15px (<16) | form-controls |
| debts / more-sheet | 375, 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div.sale-search-panel > div.sale-search-row > input.sale-search-input` | 15px (<16) | form-controls |
| debts-new / default | 375 | light | seller | touch-target | `div._app-main_9ce3y_12 > main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 111×36 | touch-targets |
| sales / default | 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| sales / default | 412 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > div._saleProductSearch_1hqfv_471 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| sales / more-sheet | 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| sales / more-sheet | 412 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > div._saleProductSearch_1hqfv_471 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| sales-new / default | 412 | light | seller | touch-target | `div._app-main_9ce3y_12 > main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 133×36 | touch-targets |
| sales-new / default | 412 | light | seller | input-font-ios-zoom | `div._saleSearchPanel_1hqfv_654 > div > div._saleSearchRow_1hqfv_660 > input._saleSearchInput_1hqfv_678` | 15px (<16) | form-controls |
| sales-new / default | 412 | light | seller | modal-actions-offscreen | `div._salePageActions_1hqfv_39 > div._salePageActionsTotal_1hqfv_58 > strong._modalFooterTotalAmount_1hqfv_16 > span._modalFooterTotalCurrency_1hqfv_27` | bottom=1171 vh=852 | modal-sheet |
| sales-new / more-sheet | 412 | light | seller | touch-target | `div._app-main_9ce3y_12 > main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 133×36 | touch-targets |
| sales-new / more-sheet | 412 | light | seller | input-font-ios-zoom | `div._saleSearchPanel_1hqfv_654 > div > div._saleSearchRow_1hqfv_660 > input._saleSearchInput_1hqfv_678` | 15px (<16) | form-controls |
| sales-new / more-sheet | 412 | light | seller | modal-actions-offscreen | `div._salePageActions_1hqfv_39 > div._salePageActionsTotal_1hqfv_58 > strong._modalFooterTotalAmount_1hqfv_16 > span._modalFooterTotalCurrency_1hqfv_27` | bottom=1171 vh=852 | modal-sheet |
| stock-history / default | 412 | light | seller | touch-target | `div._app-main_9ce3y_12 > main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 95×36 | touch-targets |
| orders / default | 412 | light | seller | touch-target | `main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > div._card_ahbvh_77._cardFull_ahbvh_86 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 28×28 | touch-targets |
| orders-new / default | 412 | light | seller | touch-target | `div._app-main_9ce3y_12 > main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > a._backLink_ahbvh_134` | 120×36 | touch-targets |
| orders-new / default | 412 | light | seller | touch-target | `main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_ahbvh_6 > form._form_ahbvh_12 > button.btn._btn-primary_1kbmi_6` | 129×42 | touch-targets |
| orders-storefront / default | 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| orders-storefront / default | 412 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > div._saleProductSearch_1hqfv_471 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| storefront-manage / default | 412 | light | seller | input-font-ios-zoom | `div._stack_ahbvh_6 > div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| storefront-manage / default | 412 | light | seller | input-font-ios-zoom | `div._saleFiltersBar_1hqfv_399 > div._saleFiltersScroll_1hqfv_429 > div._saleProductSearch_1hqfv_471 > input._saleClientSearch_1hqfv_448` | 14px (<16) | form-controls |
| debts-new / default | 412 | light | seller | touch-target | `div._app-main_9ce3y_12 > main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_p2kfq_6 > a._backLink_p2kfq_134` | 111×36 | touch-targets |
| debts-new / default | 412 | light | seller | touch-target | `form._form_7b257_1 > section._section_6ya23_244._reveal_6ya23_274 > div._dueDatePresets_7b257_14 > button._dueDatePreset_7b257_14` | 43×44 | touch-targets |
| debts-new / default | 412 | light | seller | touch-target | `div._stack_p2kfq_6 > form._form_7b257_1 > div._saveBar_7b257_43._reveal_6ya23_274 > button.btn._btn-primary_1kbmi_6` | 380×42 | touch-targets |

## Скриншоты

Файлы в `docs/screens/visual-audit/` (gitignored вместе с `docs/screens/`).
