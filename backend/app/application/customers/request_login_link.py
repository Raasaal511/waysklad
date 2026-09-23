from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import CustomerLoginLink
from app.infrastructure.config import settings


@dataclass(frozen=True)
class RequestCustomerLoginLinkCommand:
    phone: str


@dataclass(frozen=True)
class RequestCustomerLoginLinkResult:
    token: str
    telegram_deep_link: str


class RequestCustomerLoginLinkUseCase:
    """Покупатель вводит телефон на витрине — сервер выпускает одноразовую
    ссылку входа, ничего пока не подтверждено. Подтверждение приходит из
    Telegram-бота (см. ConfirmCustomerLoginLinkUseCase), когда покупатель сам
    открывает диалог по этой ссылке — так бот узнаёт chat_id покупателя ещё
    до того, как токен выдан."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: RequestCustomerLoginLinkCommand) -> RequestCustomerLoginLinkResult:
        if not settings.telegram_bot_username_clean:
            raise DomainError("Вход через Telegram недоступен")

        phone = Phone(cmd.phone)
        link = CustomerLoginLink.create(phone)

        async with self._uow as uow:
            await uow.customer_login_links.add(link)
            await uow.commit()

        deep_link = f"https://t.me/{settings.telegram_bot_username_clean}?start=login_{link.token}"
        return RequestCustomerLoginLinkResult(token=link.token, telegram_deep_link=deep_link)
