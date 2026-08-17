from typing import Annotated

from fastapi import Depends

from app.domain.common.notifier import INotifier
from app.infrastructure.telegram import TelegramNotifier


def get_notifier() -> INotifier:
    return TelegramNotifier()


NotifierDep = Annotated[INotifier, Depends(get_notifier)]
