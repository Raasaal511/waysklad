"""Смена номера вошедшим покупателем — запрос и подтверждение.

Два use case вместо одного: запрос приходит с сайта (покупатель авторизован
JWT), подтверждение — из бота (авторизации нет, есть только токен из
deep-link). Один класс обслуживал бы два разных входа с разными правилами.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import ContactCheck, Phone
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import CustomerPhoneChange
from app.infrastructure.config import settings


@dataclass(frozen=True)
class RequestCustomerPhoneChangeCommand:
    customer_id: int
    new_phone: str


@dataclass(frozen=True)
class RequestCustomerPhoneChangeResult:
    token: str
    telegram_deep_link: str


PHONE_CHANGE_PREFIX = "chphone_"


class RequestCustomerPhoneChangeUseCase:
    """Покупатель вводит новый номер в профиле — выдаём ссылку на бота.

    Здесь ничего не меняется: номер станет новым только после того, как
    владелец этого номера подтвердит его контактом в Telegram."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(
        self, cmd: RequestCustomerPhoneChangeCommand
    ) -> RequestCustomerPhoneChangeResult:
        if not settings.telegram_bot_username_clean:
            raise DomainError("Смена номера через Telegram недоступна")

        new_phone = Phone(cmd.new_phone)

        async with self._uow as uow:
            customer = await uow.customers.get(cmd.customer_id)
            if customer.phone == new_phone:
                raise DomainError("Это ваш текущий номер")

            # номер уникален в БД: без этой проверки упали бы с ошибкой
            # целостности уже после подтверждения, когда менять поздно
            taken = await uow.customers.get_by_phone(str(new_phone))
            if taken is not None and taken.id != customer.id:
                raise DomainError(
                    "На этот номер уже зарегистрирован аккаунт — "
                    "войдите в него или укажите другой номер"
                )

            change = CustomerPhoneChange.create(customer.id, new_phone)
            await uow.customer_phone_changes.add(change)
            await uow.commit()

        deep_link = (
            f"https://t.me/{settings.telegram_bot_username_clean}"
            f"?start={PHONE_CHANGE_PREFIX}{change.token}"
        )
        return RequestCustomerPhoneChangeResult(token=change.token, telegram_deep_link=deep_link)


@dataclass(frozen=True)
class ConfirmCustomerPhoneChangeCommand:
    token: str
    telegram_chat_id: str
    contact_phone: str
    contact_user_id: str
    sender_user_id: str


class ConfirmCustomerPhoneChangeUseCase:
    """Вызывается ботом, когда покупатель поделился контактом по ссылке
    смены номера.

    Сверяем контакт с НОВЫМ номером: подтверждает тот, кто им владеет.
    Сверка со старым позволила бы увести аккаунт на чужой телефон, имея
    доступ лишь к прежнему."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, cmd: ConfirmCustomerPhoneChangeCommand) -> None:
        async with self._uow as uow:
            change = await uow.customer_phone_changes.get_by_token(cmd.token)
            if change is None:
                raise DomainError("Ссылка смены номера не найдена")
            change.ensure_usable()

            check = change.check_contact(
                cmd.contact_phone, cmd.contact_user_id, cmd.sender_user_id
            )
            if check is ContactCheck.NOT_OWN:
                raise DomainError("Это чужой контакт — нажмите кнопку «Поделиться номером»")
            if check is ContactCheck.PHONE_MISMATCH:
                raise DomainError(
                    "Номер этого Telegram не совпадает с новым номером, "
                    "указанным на сайте — откройте бота с того аккаунта, "
                    "на который оформлен новый номер"
                )

            # между запросом и подтверждением номер мог занять кто-то ещё
            taken = await uow.customers.get_by_phone(str(change.new_phone))
            if taken is not None and taken.id != change.customer_id:
                raise DomainError("На этот номер уже зарегистрирован аккаунт")

            customer = await uow.customers.get(change.customer_id)
            customer.phone = change.new_phone
            customer.telegram_chat_id = cmd.telegram_chat_id
            customer.mark_phone_verified(datetime.now(timezone.utc))
            await uow.customers.save(customer)

            change.confirm()
            await uow.customer_phone_changes.save(change)
            await uow.commit()
