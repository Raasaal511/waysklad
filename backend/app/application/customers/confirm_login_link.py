from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import Customer


@dataclass(frozen=True)
class ConfirmCustomerLoginLinkCommand:
    token: str
    telegram_chat_id: str


class ConfirmCustomerLoginLinkUseCase:
    """Вызывается ботом (handlers/start.py), когда покупатель открывает
    диалог по deep-link t.me/<bot>?start=login_<token> — это единственный
    момент, когда сервер узнаёт chat_id покупателя и может считать номер
    телефона подтверждённым. Создаёт Customer при первом входе, находит
    существующего при повторном (по номеру телефона)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: ConfirmCustomerLoginLinkCommand) -> None:
        async with self._uow as uow:
            link = await uow.customer_login_links.get_by_token(cmd.token)
            if link is None:
                raise DomainError("Ссылка входа не найдена или уже использована")
            if link.is_expired:
                raise DomainError("Ссылка входа устарела — запросите новую")
            if link.is_confirmed:
                raise DomainError("Ссылка входа уже использована")

            customer = await uow.customers.get_by_phone(str(link.phone))
            if customer is None:
                customer = Customer(id=None, phone=link.phone, telegram_chat_id=cmd.telegram_chat_id)
                await uow.customers.add(customer)
            elif customer.telegram_chat_id != cmd.telegram_chat_id:
                customer.telegram_chat_id = cmd.telegram_chat_id
                await uow.customers.save(customer)

            link.confirm(customer.id)
            await uow.customer_login_links.save(link)
            await uow.commit()
