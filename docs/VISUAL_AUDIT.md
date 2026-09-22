# Визуальный аудит (блок 4.5)

Дата: 2026-09-22T21:12:57.634Z
База: `http://localhost:5173`
Всего проблем (с повторами по ширинам/темам): **31**
Уникальных корней: **1**

## Топ корней

| # | Корень | Кол-во |
|---|--------|--------|
| 1 | `touch-targets` | 31 |

## Таблица проблем

| Страница / состояние | Ширина | Тема | Роль | Проблема | Элемент | Деталь | Корень |
|---------------------|--------|------|------|----------|---------|--------|--------|
| privacy / default | 375, 412 | light | anon | touch-target | `div._auth-screen_1e286_3 > div._auth-card_1e286_42 > p > a` | 134×18 | touch-targets |
| store-catalog / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-cart / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-favorites / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| store-login / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| account / default | 375, 412 | light | anon | touch-target | `footer._footer_nbni4_3 > div._inner_nbni4_15 > div._shopBlock_nbni4_33 > a._link_nbni4_56` | 343×20 | touch-targets |
| products-new / default | 375, 412 | light | owner | touch-target | `div._heroHeading_6ya23_58 > div._heroTags_6ya23_75 > label._skuEdit_5w4jp_188 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 26×26 | touch-targets |
| products-new / default | 375, 412 | light | owner | touch-target | `div._heroBody_6ya23_37 > div._heroMeta_6ya23_118._metaEdit_5w4jp_270 > label._metaField_5w4jp_274 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 27×27 | touch-targets |
| products-new / default | 375, 412 | light | owner | touch-target | `label._metric_6ya23_132 > span._metricBody_6ya23_185 > span._metricLabelWithHint_5w4jp_91 > button._info-hint-trigger_tbth3_3` | 15×44 | touch-targets |
| orders / default | 375, 412 | light | owner | touch-target | `main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_wn974_6 > div._card_wn974_77._cardFull_wn974_86 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 28×28 | touch-targets |
| orders-new / default | 375, 412 | light | owner | touch-target | `main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_wn974_6 > form._form_wn974_12 > button.btn._btn-primary_1kbmi_6` | 129×42 | touch-targets |
| debts-new / default | 412 | light | owner | touch-target | `form._form_1h8v5_1 > section._section_6ya23_244._reveal_6ya23_274 > div._dueDatePresets_1h8v5_14 > button._dueDatePreset_1h8v5_14` | 43×44 | touch-targets |
| orders / default | 375, 412 | light | seller | touch-target | `main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_wn974_6 > div._card_wn974_77._cardFull_wn974_86 > button._icon-button_oexw4_3._icon-button-muted_oexw4_22` | 28×28 | touch-targets |
| orders-new / default | 375, 412 | light | seller | touch-target | `main._app-content_9ce3y_128._app-content-with-sell_9ce3y_162 > div._stack_wn974_6 > form._form_wn974_12 > button.btn._btn-primary_1kbmi_6` | 129×42 | touch-targets |
| debts-new / default | 375, 412 | light | seller | touch-target | `form._form_1h8v5_1 > section._section_6ya23_244._reveal_6ya23_274 > div._dueDatePresets_1h8v5_14 > button._dueDatePreset_1h8v5_14` | 43×44 | touch-targets |

## Скриншоты

Файлы в `docs/screens/visual-audit/` (gitignored вместе с `docs/screens/`).

## Исключения (не убираем сейчас)

Остаток после шага 2 (QUICK-прогон): только `touch-targets` на второстепенных
контролах. Критичные корни с `/products` (шапка, «+», EmptyState, «Продать»,
горизонтальный scroll) закрыты.

| Что | Почему оставляем |
|-----|------------------|
| Ссылки в футере витрины и на `/privacy` (высота ~18–20px) | Текстовые ссылки в абзаце/футере; раздувать до 44px ломает типографику. Основные действия — кнопки ≥44px. |
| IconButton 26–28px рядом с inline-полями SKU/метрик на форме товара | Компактный «карандаш» внутри строки героя; соседние инпуты на телефоне уже ≥44× и 16px. |
| Кнопка «+» в шапке колонки канбана заказов (28×28) | Второстепенный add в колонке; главное «+ Заказ» в заголовке страницы — 44px. |
| Метрика с подсказкой (15×44) на форме товара | Узкий hit-area у `has-hint`; сама метрика не основной CTA. |

Полный матричный прогон (все ширины + dark): `cd frontend && node scripts/visual-audit.mjs`
