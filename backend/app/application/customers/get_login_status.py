from dataclasses import dataclass

from app.domain.common.uow import IUnitOfWork
from app.infrastructure.security import create_customer_access_token


@dataclass(frozen=True)
class GetCustomerLoginStatusCommand:
    token: str


@dataclass(frozen=True)
class CustomerLoginStatusResult:
    confirmed: bool
    access_token: str | None = None


class GetCustomerLoginStatusUseCase:
    """Фронт поллит этот эндпоинт, пока покупатель не подтвердит вход в
    Telegram-боте — как только подтверждено, выдаёт обычный JWT для
    дальнейших запросов (см. security.create_customer_access_token)."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: GetCustomerLoginStatusCommand) -> CustomerLoginStatusResult:
        async with self._uow as uow:
            link = await uow.customer_login_links.get_by_token(cmd.token)
            if link is None or link.is_expired or not link.is_confirmed:
                return CustomerLoginStatusResult(confirmed=False)

            token_version = await uow.customers.get_token_version(link.customer_id)

        access_token = create_customer_access_token(link.customer_id, token_version or 0)
        return CustomerLoginStatusResult(confirmed=True, access_token=access_token)
