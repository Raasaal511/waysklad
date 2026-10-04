from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor
from app.application.notifications.push import push_to_device
from app.domain.notifications.push import IPushSender, PushMessage, PushSubscription


@dataclass
class SubscribePushCommand:
    endpoint: str
    p256dh: str
    auth: str


class SubscribePushUseCase:
    """Включить уведомления на этом устройстве. Повторный вызов с тем же
    endpoint (кабинет сверяет подписку при каждом открытии) — обновление, а не
    дубль; права не нужны — каждый получает только свои уведомления."""

    def __init__(self, uow: IUnitOfWork, sender: IPushSender):
        self._uow = uow
        self._sender = sender

    async def execute(self, actor: Actor, cmd: SubscribePushCommand) -> PushSubscription:
        if self._sender.public_key is None:
            raise DomainError("Уведомления на телефон пока не настроены на сервере")
        async with self._uow as uow:
            user = await uow.users.get(actor.id)
            subscription = PushSubscription(
                id=None,
                user_id=actor.id,
                endpoint=cmd.endpoint.strip(),
                p256dh=cmd.p256dh.strip(),
                auth=cmd.auth.strip(),
                token_version=user.token_version,
            )
            subscription.validate()
            saved = await uow.push_subscriptions.upsert(subscription)
            await uow.commit()
            return saved


class UnsubscribePushUseCase:
    """Выключить уведомления на этом устройстве (кнопка в профиле или выход
    из кабинета). Чужую подписку снять нельзя — удаляется только своя."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, endpoint: str) -> bool:
        async with self._uow as uow:
            removed = await uow.push_subscriptions.delete_for_user(actor.id, endpoint.strip())
            await uow.commit()
            return removed


class SendTestPushUseCase:
    """Пробное уведомление сразу после включения — владелец видит на своём
    телефоне, как будет выглядеть заявка, и что вся цепочка (ключи, push-сервис,
    разрешение браузера) работает. Только на это устройство."""

    def __init__(self, uow: IUnitOfWork, sender: IPushSender):
        self._uow = uow
        self._sender = sender

    async def execute(self, actor: Actor, endpoint: str) -> bool:
        async with self._uow as uow:
            delivered = await push_to_device(
                uow,
                self._sender,
                recipient=await uow.users.get(actor.id),
                endpoint=endpoint.strip(),
                message=PushMessage(
                    title="Уведомления включены",
                    body="Так придёт новая заявка с витрины, даже когда кабинет закрыт",
                    link="/profile",
                    tag="push-test",
                ),
            )
            # мёртвая подписка удалена внутри push_to_user — фиксируем
            await uow.commit()
            return delivered
