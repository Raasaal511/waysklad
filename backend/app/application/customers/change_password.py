from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.customers.entities import Customer
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.security import (
    create_customer_access_token,
    hash_password,
    verify_password,
)

MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class ChangeCustomerPasswordCommand:
    customer_id: int
    new_password: str
    # None — аккаунт без пароля (заведён входом через Telegram): пароль
    # устанавливается впервые, подтверждать нечем
    current_password: str | None = None


@dataclass(frozen=True)
class ChangeCustomerPasswordResult:
    customer: Customer
    access_token: str


class ChangeCustomerPasswordUseCase:
    """Смена пароля покупателя — или установка, если пароля не было.

    Как и у владельца, смена инкрементирует token_version (разлогинивает все
    устройства) и сразу выдаёт свежий токен: иначе покупатель разлогинил бы
    сам себя этим же запросом.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(
        self, cmd: ChangeCustomerPasswordCommand
    ) -> ChangeCustomerPasswordResult:
        if len(cmd.new_password) < MIN_PASSWORD_LENGTH:
            raise DomainError(f"Пароль короче {MIN_PASSWORD_LENGTH} символов")

        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            customer = await uow.customers.get(cmd.customer_id)

            if customer.has_password:
                if not cmd.current_password:
                    raise DomainError("Укажите текущий пароль")
                if not verify_password(cmd.current_password, customer.password_hash):
                    raise DomainError("Текущий пароль неверен")

            customer.set_password(hash_password(cmd.new_password))
            customer.token_version += 1
            await uow.customers.save(customer)
            await uow.commit()

        token = create_customer_access_token(customer.id, customer.token_version)
        return ChangeCustomerPasswordResult(customer=customer, access_token=token)


class LogoutAllCustomerUseCase:
    """Отозвать все токены покупателя — включая тот, которым вызван запрос
    (тот же смысл, что LogoutAllUseCase у владельца)."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, customer_id: int) -> None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            customer = await uow.customers.get(customer_id)
            customer.token_version += 1
            await uow.customers.save(customer)
            await uow.commit()
