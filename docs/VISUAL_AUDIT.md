# Визуальный аудит (блок 4.5)

Дата: 2026-09-23T09:35:50.114Z
База: `http://localhost:5173`
Всего проблем (с повторами по ширинам/темам): **18**
Уникальных корней: **2**

## Сводка после правок

**Было 24 → стало 18.** `fixed-stacking` 6 → 0. На sales-new и products-new
срабатываний нет. Все 18 оставшихся — старые проблемы аналитики на телефоне
(см. ниже).

| Корень | Было | Стало | Что сделано |
|--------|------|-------|-------------|
| `fixed-stacking` | 6 | 0 | С 11.08 не работал ни один `position: sticky`: `overflow-x: hidden` у html/body делал body отдельным scroll-контейнером. Теперь `clip`. Панель продажи стоит над меню вместе с FAB (`--app-nav-clearance`), при открытой клавиатуре возвращается в поток, меню скрывается. |
| `touch-targets` | 18 | 12 | products-new: поле штрихкода занимает всю строку (input был 4px), у «i» зона 44×44. Оставшиеся 12 — столбики графика аналитики. |
| `text-ellipsis` | 0 | 6 | Новые срабатывания: таблицы аналитики на 320–360px. |
| `typography-min` | 0 | 0 | В промежуточном прогоне всплыло 15 на графике аналитики, подписи подняты до 12px. |

### Оставшиеся 18: аналитика на телефоне, проблемы старше этой задачи

Раньше аудит их не видел: график и таблицы не успевали загрузиться за 400 мс
после открытия страницы. Сейчас срабатывания тоже нестабильны и скачут по
ширинам и темам. Исправление записано в «Не вошло» `TASK_RELEASE_V1.md`.

- Столбики графика по месяцам на 320–412px шириной 12–15px: 12 колонок в ~250px.
- Таблицы «Топ товаров» и «Замороженный товар» на 320–360px: строка шире
  карточки на 9–21px, у `.dataTable` стоит `overflow: hidden`, поэтому правая
  колонка обрезается.

## Топ корней

| # | Корень | Кол-во |
|---|--------|--------|
| 1 | `touch-targets` | 12 |
| 2 | `text-ellipsis` | 6 |

## Таблица проблем

| Страница / состояние | Ширина | Тема | Роль | Проблема | Элемент | Деталь | Корень |
|---------------------|--------|------|------|----------|---------|--------|--------|
| analytics / default | 320, 360 | light | owner | clipped-text | `main._app-content_1v7hr_138._app-content-with-sell_1v7hr_172 > div._stack_bb66d_6 > div._stack_bb66d_6 > div._dataTable_bb66d_199` | scrollW=307 clientW=286 text="ТоварОстатокЗамороженоБез продажСумка ко" | text-ellipsis |
| analytics / default | 360, 412 | light | owner | touch-target | `div._plotRow_hxmuv_7 > div._plotArea_hxmuv_32 > div._plot_hxmuv_7 > button._barCol_hxmuv_67` | 15×223 | touch-targets |
| analytics / default | 320, 360, 393, 412 | dark | owner | touch-target | `div._plotRow_hxmuv_7 > div._plotArea_hxmuv_32 > div._plot_hxmuv_7 > button._barCol_hxmuv_67` | 12×223 | touch-targets |
| analytics / default | 320, 360 | dark | owner | clipped-text | `main._app-content_1v7hr_138._app-content-with-sell_1v7hr_172 > div._stack_bb66d_6 > div._stack_bb66d_6 > div._dataTable_bb66d_199` | scrollW=295 clientW=286 text="ТоварПроданоВыручкаСр. чекДоляПлатье лет" | text-ellipsis |

## Скриншоты

Файлы в `docs/screens/visual-audit/` (gitignored вместе с `docs/screens/`).
