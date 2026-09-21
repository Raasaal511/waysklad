from dataclasses import dataclass

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import CustomerLoginLink, validate_username
from app.infrastructure.config import settings
from app.infrastructure.security import hash_password

MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class RegisterCustomerCommand:
    username: str
    phone: str
    password: str
    password_confirm: str


@dataclass(frozen=True)
class RegisterCustomerResult:
    """Токена здесь нет: аккаунт ещё не создан — его создаст бот, когда
    покупатель подтвердит номер по deep-link (ConfirmCustomerLoginLink).
    Фронт опрашивает /login-status тем же способом, что и при обычном входе."""

    token: str
    telegram_deep_link: str


class RegisterCustomerUseCase:
    """Регистрация покупателя: username + телефон + пароль, подтверждение
    номера — в Telegram-боте платформы.

    Аккаунт намеренно не создаётся здесь: пока покупатель не открыл диалог с
    ботом, номер не подтверждён, и регистрация на чужой телефон была бы
    возможна. Данные ждут в CustomerLoginLink (TTL 10 минут), аккаунт
    появляется в момент подтверждения.

    Занятость username и телефона проверяется дважды — здесь, чтобы сразу
    показать ошибку в форме, и при подтверждении, потому что между двумя
    моментами кто-то мог занять то же имя.
    """

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: RegisterCustomerCommand) -> RegisterCustomerResult:
        if not settings.telegram_bot_username_clean:
            raise DomainError("Регистрация недоступна: не настроен Telegram-бот")

        username = validate_username(cmd.username)

        if cmd.password != cmd.password_confirm:
            raise DomainError("Пароли не совпадают")
        if len(cmd.password) < MIN_PASSWORD_LENGTH:
            raise DomainError(f"Пароль короче {MIN_PASSWORD_LENGTH} символов")

        phone = Phone(cmd.phone)

        async with self._uow as uow:
            if await uow.customers.get_by_username(username) is not None:
                raise DomainError("Имя пользователя занято")
            existing = await uow.customers.get_by_phone(str(phone))
            if existing is not None and existing.has_password:
                raise DomainError("Этот телефон уже зарегистрирован")

            link = CustomerLoginLink.create_for_registration(
                phone, username, hash_password(cmd.password)
            )
            await uow.customer_login_links.add(link)
            await uow.commit()

        deep_link = f"https://t.me/{settings.telegram_bot_username_clean}?start=login_{link.token}"
        return RegisterCustomerResult(token=link.token, telegram_deep_link=deep_link)
