from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import Customer
from app.infrastructure.security import create_customer_access_token, verify_password


@dataclass(frozen=True)
class LoginCustomerCommand:
    """login — username или телефон: покупатель регистрировался с обоими и
    помнит что-то одно, а различить их можно без подсказки (телефон не проходит
    валидацию username и наоборот)."""

    login: str
    password: str


@dataclass(frozen=True)
class LoginCustomerResult:
    customer: Customer
    access_token: str


class LoginCustomerUseCase:
    """Вход покупателя по username или телефону и паролю.

    Текст ошибки один и тот же для «нет такого логина», «пароль не задан»
    и «пароль неверный» — иначе форма входа превращается в проверку, какие
    номера и логины зарегистрированы на платформе.
    """

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: LoginCustomerCommand) -> LoginCustomerResult:
        login = cmd.login.strip()

        async with self._uow as uow:
            customer = await uow.customers.get_by_username(login)
            if customer is None:
                # не username — пробуем как телефон; неразбираемый номер это
                # та же «неверный логин или пароль», а не отдельная ошибка формы
                try:
                    phone = Phone(login)
                except DomainError:
                    phone = None
                if phone is not None:
                    customer = await uow.customers.get_by_phone(str(phone))

        if (
            customer is None
            or not customer.has_password
            or not verify_password(cmd.password, customer.password_hash)
        ):
            raise DomainError("Неверный логин или пароль")

        assert customer.id is not None
        token = create_customer_access_token(customer.id, customer.token_version)
        return LoginCustomerResult(customer=customer, access_token=token)
