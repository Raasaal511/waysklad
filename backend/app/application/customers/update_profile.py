from dataclasses import dataclass

from app.domain.customers.entities import Customer
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class UpdateCustomerProfileCommand:
    customer_id: int
    name: str


class UpdateCustomerProfileUseCase:
    """Покупатель редактирует имя.

    Телефон руками не меняется: он приходит из контакта Telegram при входе
    (ConfirmCustomerLoginLinkUseCase) и служит идентичностью аккаунта. Пока
    поле было редактируемым, в заявку магазину мог попасть любой чужой или
    выдуманный номер — код уходил в Telegram покупателя и «подтверждал» его.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: UpdateCustomerProfileCommand) -> Customer:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            customer = await uow.customers.get(cmd.customer_id)
            customer.update_name(cmd.name)
            await uow.customers.save(customer)
            await uow.commit()
            return customer
