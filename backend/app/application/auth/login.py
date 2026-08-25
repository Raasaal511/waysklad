from dataclasses import dataclass

from app.domain.common.exceptions import AccessDeniedError, DomainError
from app.domain.common.phone import Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import User
from app.domain.identity.ports import IPasswordHasher


@dataclass(frozen=True)
class LoginCommand:
    phone: str
    password: str


class LoginUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, cmd: LoginCommand) -> User:
        try:
            phone = Phone(cmd.phone)
        except DomainError:
            raise AccessDeniedError("Неверный телефон или пароль")

        async with self._uow as uow:
            user = await uow.users.get_by_phone(str(phone))

        if (
            user is None
            or not user.is_active
            or not self._hasher.verify(cmd.password, user.password_hash)
        ):
            raise AccessDeniedError("Неверный телефон или пароль")
        return user
