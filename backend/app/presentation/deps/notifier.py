from typing import Annotated

from fastapi import Depends

from app.domain.common.notifier import INotifier
from app.domain.notifications.push import IPushSender
from app.infrastructure.notifications import web_push
from app.infrastructure.notifications.telegram import TelegramNotifier


def get_notifier() -> INotifier:
    return TelegramNotifier()


NotifierDep = Annotated[INotifier, Depends(get_notifier)]


def get_push_sender() -> IPushSender:
    # атрибут модуля, а не импорт объекта — тесты подменяют web_push.push_sender
    return web_push.push_sender


PushSenderDep = Annotated[IPushSender, Depends(get_push_sender)]
