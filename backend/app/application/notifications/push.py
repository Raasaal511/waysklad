import asyncio
import logging

from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import User
from app.domain.notifications.entities import NotificationKind
from app.domain.notifications.push import (
    IPushSender,
    PushDeliveryResult,
    PushMessage,
    PushSubscription,
)

_logger = logging.getLogger(__name__)

# Заголовок — то, что видно на экране блокировки первым; текст уведомления
# из колокольчика идёт строкой ниже.
PUSH_TITLES: dict[NotificationKind, str] = {
    NotificationKind.STOREFRONT_REQUEST_NEW: "Новая заявка с витрины",
    NotificationKind.STOREFRONT_MESSAGE: "Сообщение от покупателя",
    NotificationKind.LOW_STOCK: "Товар заканчивается",
    NotificationKind.DEBT_ISSUED: "Новый долг",
    NotificationKind.DEBT_DUE_SOON: "Скоро срок долга",
    NotificationKind.DEBT_OVERDUE: "Долг просрочен",
    NotificationKind.TASK_ASSIGNED: "Новая задача",
    NotificationKind.TASK_DONE: "Задача выполнена",
}

# покупатель ждёт ответа — эти уведомления будят телефон сразу
_URGENT_KINDS = {NotificationKind.STOREFRONT_REQUEST_NEW, NotificationKind.STOREFRONT_MESSAGE}


def build_push_message(
    kind: NotificationKind, text: str, link: str, tag: str
) -> PushMessage:
    title = PUSH_TITLES.get(kind, "WaySklad")
    # «Новая заявка с витрины: Иван, …» под заголовком «Новая заявка с витрины»
    # повторяет его — на узком экране блокировки остаётся только суть
    body = text.removeprefix(f"{title}: ")
    return PushMessage(
        title=title, body=body, link=link or "/", tag=tag, urgent=kind in _URGENT_KINDS
    )


async def _live_subscriptions(
    uow: IUnitOfWork, recipient: User, endpoint: str | None = None
) -> list[PushSubscription]:
    """Подписки, на которые можно слать; устаревшие удаляет в той же транзакции."""
    subscriptions = await uow.push_subscriptions.list_for_user(recipient.id)
    if endpoint is not None:
        subscriptions = [s for s in subscriptions if s.endpoint == endpoint]
    live = []
    for subscription in subscriptions:
        # заблокированный сотрудник или чужая сессия (сменил пароль, «завершить
        # все сессии») — на это устройство больше ничего не уходит
        if not recipient.is_active or subscription.token_version != recipient.token_version:
            await uow.push_subscriptions.delete(subscription.id)
        else:
            live.append(subscription)
    return live


async def _send_all(
    sender: IPushSender, subscriptions: list[PushSubscription], message: PushMessage
) -> tuple[int, list[PushSubscription]]:
    """Отправить на все устройства разом. Не бросает. Возвращает (доставлено, умершие)."""
    results = await asyncio.gather(
        *(sender.send(s, message) for s in subscriptions), return_exceptions=True
    )
    delivered, gone = 0, []
    for subscription, result in zip(subscriptions, results):
        if isinstance(result, BaseException):
            _logger.warning("Web Push sender raised", exc_info=result)
        elif result is PushDeliveryResult.GONE:
            gone.append(subscription)
        elif result is PushDeliveryResult.DELIVERED:
            delivered += 1
    return delivered, gone


async def _deliver_after_commit(
    uow: IUnitOfWork, sender: IPushSender, subscriptions: list[PushSubscription], message: PushMessage
) -> None:
    _, gone = await _send_all(sender, subscriptions, message)
    if not gone:
        return
    async with uow:
        for subscription in gone:
            await uow.push_subscriptions.delete(subscription.id)
        await uow.commit()


async def push_to_user(
    uow: IUnitOfWork, sender: IPushSender, *, recipient: User, message: PushMessage
) -> None:
    """Уведомление на все устройства сотрудника. В транзакции операции — только
    выборка подписок; сама отправка идёт после commit в фоне: заявка покупателя
    не ждёт ответа Google/Apple и не держит на это время блокировки остатков,
    а откатившаяся операция ничего не присылает."""
    if sender.public_key is None:
        return  # push не настроен на сервере — без лишних запросов к БД
    live = await _live_subscriptions(uow, recipient)
    if live:
        background = uow.fork()
        uow.after_commit(lambda: _deliver_after_commit(background, sender, live, message))


async def push_to_device(
    uow: IUnitOfWork, sender: IPushSender, *, recipient: User, endpoint: str, message: PushMessage
) -> bool:
    """Сразу, с ответом — для пробного уведомления, где человек ждёт результата.
    Дошло ли до push-сервиса; умершую подписку удаляет в этой же транзакции."""
    if sender.public_key is None:
        return False
    live = await _live_subscriptions(uow, recipient, endpoint)
    if not live:
        return False
    delivered, gone = await _send_all(sender, live, message)
    for subscription in gone:
        await uow.push_subscriptions.delete(subscription.id)
    return delivered > 0
