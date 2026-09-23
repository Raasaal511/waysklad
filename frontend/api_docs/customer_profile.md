Написано для: фронтенд-разработчика, который делает личный кабинет покупателя `/account`.

# Личный кабинет покупателя: профиль, подтверждение телефона, заказы, чаты

Задача `docs/TASK_CUSTOMER_PROFILE.md`, часть A. Все эндпоинты требуют JWT
покупателя (`Authorization: Bearer <token>`), кроме особо отмеченных.

Регистрация и вход описаны отдельно — см. `customer_auth.md`.

---

## Коды ответов, общие для всего документа

| Код | Когда | Что показать |
|-----|-------|--------------|
| `400` | Ошибка ввода или состояния | `detail` — готовый текст для пользователя |
| `401` | Токен истёк или отозван | Экран входа |
| `403` | Чужой объект | «Нет доступа» |
| `404` | Объекта нет | «Не найдено» |
| `429` | Лимит частоты или попыток | `detail` + таймер из `retry_after` |

Тело ошибки всегда `{ "detail": string }`. У `429` добавляется
`retry_after: number` (секунды) и заголовок `Retry-After`.

---

## 1. Профиль

### `GET /api/auth/customer/me`

```ts
interface CustomerProfile {
  id: number
  phone: string
  name: string
  username: string          // "" у аккаунтов, заведённых входом через Telegram
  phone_verified: boolean
  phone_verified_at: string | null   // ISO 8601
  created_at: string | null          // ISO 8601, «с нами с …»
  has_password: boolean              // false — вход только через Telegram
  stats: {
    requests_total: number
    requests_accepted: number
    requests_rejected: number
    requests_active: number          // заявки в статусе new
    shops_count: number              // в скольких магазинах заказывал
  }
}
```

### `PUT /api/auth/customer/me`

```ts
interface UpdateProfileRequest {
  name: string              // 1..200, обязателен
  phone?: string | null     // не передан — номер не трогаем
}

interface CustomerShort {
  id: number
  phone: string
  name: string
  username: string
  phone_verified: boolean
}
```

**Важно для UI:** смена телефона сбрасывает `phone_verified` в `false` —
подтверждён был старый номер. Предупредите об этом в форме до отправки.
Ответ уже содержит `phone_verified`, перезапрашивать профиль не нужно.

Занятый другим аккаунтом номер → `400` «Этот телефон уже занят другим
аккаунтом».

---

## 2. Подтверждение телефона кодом

Код отправляется в Telegram-бот платформы (SMS пока нет — см. «Что дальше»).

### `POST /api/auth/customer/phone/request-code`

Тело пустое: телефон берётся из аккаунта, иначе кодом можно было бы засыпать
чужой номер.

```ts
interface RequestCodeResponse {
  sent_via: 'telegram' | 'console'
  retry_after: number          // секунды до следующей отправки (обычно 60)
  telegram_deep_link: string   // непусто → см. ниже
}
```

**Два сценария ответа:**

1. `telegram_deep_link` **пуст** — код отправлен. Показывайте экран ввода кода
   и таймер на `retry_after` секунд.
2. `telegram_deep_link` **непуст** — у покупателя нет привязанного Telegram,
   слать некуда. Покажите экран «Откройте бота и нажмите Старт» с кнопкой на
   эту ссылку и иллюстрацией `state-telegram-confirm`. Код при этом **не
   выпущен** и лимит не потрачен: после возвращения из бота запросите код
   ещё раз.

**Лимиты:** не чаще раза в 60 секунд (`429` с `retry_after`), не больше 5
запросов в час (`429`, `retry_after: 3600`).

### `POST /api/auth/customer/phone/verify`

```ts
interface VerifyCodeRequest { code: string }   // 6 цифр

interface VerifyCodeResponse {
  phone_verified: boolean
  phone_verified_at: string | null
}
```

Код живёт 5 минут, попыток ввода — 5.

| Ситуация | Код | `detail` |
|----------|-----|----------|
| Неверный код | `400` | «Неверный код, осталось попыток: N» |
| Код просрочен или не запрашивался | `400` | «Код просрочен или не запрашивался — запросите новый» |
| Попытки кончились | `429` | «Попытки закончились — запросите новый код» |
| Телефон сменили после выпуска кода | `400` | «Телефон изменился — запросите новый код» |

Все тексты готовы к показу как есть. При ошибке поле ввода **не очищайте
полностью** — подсветите клетки `--danger`, пусть покупатель исправит.

---

## 3. Список заказов

### `GET /api/storefront/requests/my`

Параметры: `status` (`new` | `accepted` | `rejected`), `limit` (по умолчанию
20, максимум 100), `offset`.

> **Ломающее изменение:** раньше эндпоинт отдавал голый массив, теперь —
> объект `{ items, total }`.

```ts
interface MyRequestsResponse {
  items: MyRequest[]
  total: number      // всего под фильтром, для бесконечной подгрузки
}

interface MyRequestLine {
  product_id: number
  name: string       // «Товар удалён», если товара больше нет
  photo: string
  quantity: string   // десятичное как строка
  price: string
  total: string
}

interface MyRequest {
  id: number
  status: 'new' | 'accepted' | 'rejected'
  customer_name: string
  note: string
  created_at: string | null

  shop_name: string
  shop_slug: string        // ссылка на витрину: /store/{shop_slug}
  shop_logo: string

  order_lines: MyRequestLine[]
  order_total: string      // сумма заявки по текущим ценам магазина

  // ниже — только у принятых заявок (status === 'accepted')
  due_date: string | null       // YYYY-MM-DD, «готово к …»
  accepted_total: string | null // сумма заказа, зафиксированная при принятии
  prepayment: string | null
  to_pay: string | null
  order_status: string | null
}
```

**Про суммы:** `order_total` пересчитывается по текущим ценам витрины, а
`accepted_total` зафиксирован в момент принятия заявки. Для принятых заказов
показывайте `accepted_total` и `to_pay` — это то, что покупатель реально
платит.

Заявки отсортированы новыми сверху. Чужие заявки не видны — фильтрация по
аккаунту на сервере.

---

## 4. Чаты

Отдельные эндпоинты по JWT. Старый путь `GET/POST /api/storefront/requests/chat?token=`
остаётся для тех, кто заказывал без регистрации, — в личном кабинете
используйте эти.

### `GET /api/auth/customer/chats`

```ts
interface ChatSummary {
  request_id: number
  shop_name: string
  shop_slug: string
  shop_logo: string
  request_status: 'new' | 'accepted' | 'rejected'
  last_message: string
  last_message_at: string | null
  last_message_from_shop: boolean   // true — последним писал магазин
  messages_count: number
}
```

Диалоги, в которых ещё не было сообщений, в список **не попадают**. Свежие
сверху.

### `GET /api/auth/customer/chats/{request_id}`

```ts
interface ChatMessage {
  id: number | null
  request_id: number
  author: 'customer' | 'staff'
  text: string
  created_at: string | null
}
```

### `POST /api/auth/customer/chats/{request_id}`

```ts
interface SendMessageRequest { text: string }   // 1..2000
```

Ответ — созданное `ChatMessage`, код `201`.

Чужая заявка → `403` (не `404`: заявка существует, просто не ваша).
Несуществующая → `404`.

**WebSocket:** сообщения уходят в тот же канал, что и при старом способе
отправки, — уже открытый сокет чата их увидит.

---

## 5. Пароль и выходы

### `PATCH /api/auth/customer/me/password`

```ts
interface ChangePasswordRequest {
  new_password: string          // минимум 8 символов
  current_password?: string     // не нужен, если has_password === false
}

interface ChangePasswordResponse {
  access_token: string          // сохраните немедленно!
}
```

**Обязательно:** смена пароля отзывает все прежние токены, включая текущий.
Сразу запишите новый `access_token` в хранилище, иначе следующий же запрос
получит `401`.

Аккаунт из Telegram-входа (`has_password === false`) задаёт пароль **без**
`current_password` — подтверждать нечем. Показывайте в этом случае форму
«Задать пароль», а не «Сменить пароль».

Неверный текущий пароль → `400` «Текущий пароль неверен».

### `POST /api/auth/customer/me/logout-all`

Ответ `204`. Отзывает **все** токены, включая тот, которым вызван запрос —
после вызова ведите на экран входа. Спросите подтверждение до вызова.

---

## Что дальше (не в этой задаче)

- **SMS вместо Telegram.** Канал доставки спрятан за интерфейсом
  (`VERIFICATION_SENDER=telegram|console`), подключение провайдера не изменит
  контракты выше — `sent_via` просто станет `'sms'`.
- **Блокировка заявок для неподтверждённых** — решение отложено, сейчас
  заказывать может любой авторизованный покупатель.
