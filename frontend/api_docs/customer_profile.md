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
  name: string              // 1..200, обязателен и единственное поле
}

interface CustomerShort {
  id: number
  phone: string
  name: string
  username: string
  phone_verified: boolean
}
```

**Важно для UI (изменено 02.10):** поля `phone` больше нет — передать его
нельзя, схема отклоняет лишние поля (422). Телефон показывается только для
чтения; менять его можно, лишь войдя с другого Telegram.

Занятый другим аккаунтом номер → `400` «Этот телефон уже занят другим
аккаунтом».

---

## 2. Телефон покупателя (обновлено 04.10)

Телефон всегда приходит из контакта Telegram — вписать его руками нельзя
нигде. `PUT /me` принимает только имя.

**Удалены 02.10:** `POST /api/auth/customer/phone/request-code` и
`POST /api/auth/customer/phone/verify`, а также команда `/confirm <код>` в боте.
Отдельный код подтверждал номер, который покупатель сам же и вписал: код уходил
в его чат с ботом, а в заявку магазину попадал любой чужой или выдуманный номер.

При входе бот по ссылке `?start=login_<token>` просит «📱 Поделиться номером» и
пускает, только если номер контакта совпал с указанным на сайте.
`phone_verified` проставляется в этот момент.

### `POST /api/auth/customer/me/phone-change` (новое 04.10)

Смена номера у вошедшего покупателя. Лимит `10/hour`.

```ts
// запрос
{ new_phone: string }

// ответ 200
{ token: string, telegram_deep_link: string }
```

Номер здесь **ещё не меняется**. Ведём покупателя по `telegram_deep_link`
(`?start=chphone_<token>`); бот просит контакт и меняет номер, только если
контакт совпал с **новым** номером. Сверка именно с новым: подтверждать
должен тот, кто им владеет, иначе аккаунт можно было бы увести на чужой
телефон, имея доступ лишь к прежнему.

Ошибки `400`: номер совпадает с текущим, номер занят другим аккаунтом,
Telegram-бот не настроен. Текст в `detail` готов к показу.

Отдельного статус-эндпоинта нет: пока окно открыто, опрашиваем `GET /me`
(раз в 2 с) и закрываем его, когда `phone` изменился. Ссылка живёт 10 минут
и одноразовая.

### Неподтверждённый номер

У покупателей, заведённых до перехода на Telegram, `phone_verified = false`.
Запретов на это нет — заказы оформляются по-прежнему. В профиле показываем
баннер с призывом подтвердить номер: ведёт в тот же `POST /me/phone-change`
(покупатель вводит свой же номер, бот его подтверждает).

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
