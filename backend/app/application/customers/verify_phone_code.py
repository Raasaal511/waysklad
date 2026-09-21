from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.common.exceptions import DomainError, TooManyAttemptsError
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import Customer
from app.infrastructure.security import verify_password


@dataclass(frozen=True)
class VerifyPhoneCodeCommand:
    customer_id: int
    code: str


class VerifyPhoneCodeUseCase:
    """Проверка кода подтверждения телефона.

    Попытки считаются на коде, а не на аккаунте: исчерпав CODE_MAX_ATTEMPTS,
    покупатель заказывает новый код, а подобрать шестизначный за пять попыток
    нереально.

    Код проверяется против номера, который был актуален при выпуске: если
    покупатель успел сменить телефон, старый код новый номер не подтвердит.
    """

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: VerifyPhoneCodeCommand) -> Customer:
        now = datetime.now(timezone.utc)
        code_input = cmd.code.strip()

        async with self._uow as uow:
            customer = await uow.customers.get(cmd.customer_id)
            if customer.phone_verified:
                raise DomainError("Телефон уже подтверждён")

            code = await uow.customer_phone_codes.get_active(customer.id, now)
            if code is None:
                raise DomainError("Код просрочен или не запрашивался — запросите новый")
            if code.attempts_left <= 0:
                raise TooManyAttemptsError("Попытки закончились — запросите новый код")
            if str(code.phone) != str(customer.phone):
                raise DomainError("Телефон изменился — запросите новый код")

            if not verify_password(code_input, code.code_hash):
                code.register_failed_attempt()
                await uow.customer_phone_codes.save(code)
                await uow.commit()
                left = code.attempts_left
                if left <= 0:
                    raise TooManyAttemptsError("Попытки закончились — запросите новый код")
                raise DomainError(f"Неверный код, осталось попыток: {left}")

            customer.mark_phone_verified(now)
            await uow.customers.save(customer)
            # код одноразовый: после успеха гасим его вместе с остальными
            await uow.customer_phone_codes.expire_active(customer.id, now)
            await uow.commit()

        return customer
