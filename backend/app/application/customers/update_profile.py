from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class UpdateCustomerProfileCommand:
    customer_id: int
    name: str
    phone: str | None = None  # None — номер не меняем


class UpdateCustomerProfileUseCase:
    """Покупатель редактирует имя и телефон.

    Телефон — идентичность аккаунта (логин и уникальный ключ), поэтому смена
    номера сбрасывает phone_verified: подтверждён был старый номер, новый
    ещё никто не проверял. Номер, занятый другим аккаунтом, отклоняется.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: UpdateCustomerProfileCommand) -> Customer:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            customer = await uow.customers.get(cmd.customer_id)
            customer.update_name(cmd.name)

            if cmd.phone is not None:
                phone = Phone(cmd.phone)
                if str(phone) != str(customer.phone):
                    occupied = await uow.customers.get_by_phone(str(phone))
                    if occupied is not None and occupied.id != customer.id:
                        raise DomainError("Этот телефон уже занят другим аккаунтом")
                    customer.change_phone(phone)

            await uow.customers.save(customer)
            await uow.commit()
            return customer
