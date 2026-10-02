from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.customers.entities import Customer


@dataclass(frozen=True)
class ConfirmCustomerLoginLinkCommand:
    token: str
    telegram_chat_id: str
    # номер из контакта Telegram и чей это контакт — бот присылает их,
    # когда покупатель нажал «Поделиться номером»
    contact_phone: str
    contact_user_id: str
    sender_user_id: str


class ConfirmCustomerLoginLinkUseCase:
    """Вызывается ботом (handlers/start.py), когда покупатель поделился
    номером после перехода по deep-link t.me/<bot>?start=login_<token>.

    Номер телефона в форме покупатель пишет руками, поэтому подтверждением
    считается не сам факт открытия диалога, а совпадение с номером аккаунта
    Telegram: иначе можно было зарегистрироваться на любой чужой номер.
    Создаёт Customer при первом входе, находит существующего при повторном."""

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
            if cmd.contact_user_id != cmd.sender_user_id:
                raise DomainError("Это чужой контакт — нажмите кнопку «Поделиться номером»")
            if not link.matches_contact(cmd.contact_phone):
                raise DomainError(
                    "Номер этого Telegram не совпадает с указанным на сайте — "
                    "исправьте номер в форме или войдите с того Telegram, на который он оформлен"
                )

            customer = await uow.customers.get_by_phone(str(link.phone))

            if link.is_registration:
                # username мог занять кто-то другой, пока покупатель шёл в бота
                taken = await uow.customers.get_by_username(link.username)
                if taken is not None and taken.id != (customer.id if customer else None):
                    raise DomainError("Имя пользователя уже занято — начните регистрацию заново")
                if customer is not None and customer.has_password:
                    raise DomainError("Этот телефон уже зарегистрирован")

            now = datetime.now(timezone.utc)
            if customer is None:
                customer = Customer(
                    id=None,
                    phone=link.phone,
                    telegram_chat_id=cmd.telegram_chat_id,
                    # номер пришёл из контакта Telegram и совпал с формой —
                    # это и есть подтверждение, отдельный код больше не нужен
                    phone_verified=True,
                    phone_verified_at=now,
                    personal_data_consent_at=(now if link.is_registration else None),
                )
                if link.is_registration:
                    customer.set_username(link.username)
                    customer.set_password(link.password_hash)
                await uow.customers.add(customer)
            else:
                changed = False
                if customer.telegram_chat_id != cmd.telegram_chat_id:
                    customer.telegram_chat_id = cmd.telegram_chat_id
                    changed = True
                if not customer.phone_verified:
                    customer.mark_phone_verified(now)
                    changed = True
                if link.is_registration:
                    # аккаунт был заведён входом через Telegram — регистрация
                    # доводит его до парольного, второй с тем же номером не нужен
                    customer.set_username(link.username)
                    customer.set_password(link.password_hash)
                    if customer.personal_data_consent_at is None:
                        customer.personal_data_consent_at = now
                    changed = True
                if changed:
                    await uow.customers.save(customer)

            link.confirm(customer.id)
            await uow.customer_login_links.save(link)
            await uow.commit()
