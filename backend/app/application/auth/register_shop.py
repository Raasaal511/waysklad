from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.common.slug import generate_slug
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, Tenant, User
from app.domain.identity.permissions import Actor
from app.domain.identity.ports import IPasswordHasher


@dataclass(frozen=True)
class RegisterShopCommand:
    shop_name: str
    owner_name: str
    phone: str
    password: str
    personal_data_consent: bool


@dataclass(frozen=True)
class RegisterShopResult:
    owner: User
    shop_slug: str


class RegisterShopUseCase:
    """Создать магазин с владельцем без Telegram — для сидов и тестов. Сайт
    регистрирует только через бота: StartSignupUseCase → CompleteSignupUseCase."""

    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, cmd: RegisterShopCommand) -> RegisterShopResult:
        phone = validate_signup(cmd)
        async with self._uow as uow:
            result = await create_shop(
                uow,
                shop_name=cmd.shop_name,
                owner_name=cmd.owner_name,
                phone=phone,
                password_hash=self._hasher.hash(cmd.password),
                consent_at=datetime.now(timezone.utc),
            )
            await uow.commit()
            return result


def validate_signup(cmd: RegisterShopCommand) -> Phone:
    """Проверки формы регистрации — до бота, чтобы не гонять человека в
    Telegram с заведомо неверными данными."""
    if not cmd.personal_data_consent:
        raise DomainError("Нужно согласие на обработку персональных данных")
    if not cmd.shop_name.strip():
        raise DomainError("Укажите название магазина")
    if not cmd.owner_name.strip():
        raise DomainError("Укажите ваше имя")
    if len(cmd.password) < 6:
        raise DomainError("Пароль должен быть не короче 6 символов")
    return Phone(cmd.phone)


async def create_shop(
    uow: IUnitOfWork,
    *,
    shop_name: str,
    owner_name: str,
    phone: Phone,
    password_hash: str,
    consent_at: datetime,
    telegram_user_id: str | None = None,
    telegram_chat_id: str | None = None,
) -> RegisterShopResult:
    """Магазин + владелец в открытой транзакции uow (commit — у вызывающего).
    Telegram, подтверждённый ботом, сразу становится каналом сводок и уведомлений."""
    if await uow.users.get_by_phone(str(phone)) is not None:
        raise DomainError("Этот телефон уже зарегистрирован")

    slug = await _unique_slug(uow, shop_name)
    tenant = await uow.tenants.add(
        Tenant(
            id=None,
            name=shop_name.strip(),
            slug=slug,
            owner_telegram_chat_id=telegram_chat_id,
        )
    )
    uow.tenant_id = tenant.id

    now = datetime.now(timezone.utc)
    owner = await uow.users.add(
        User(
            id=None,
            name=owner_name.strip(),
            phone=phone,
            role=Role.OWNER,
            password_hash=password_hash,
            personal_data_consent_at=consent_at,
            telegram_user_id=telegram_user_id,
            telegram_verified_at=now if telegram_user_id else None,
        )
    )
    await uow.audit.add(
        AuditEntry.record(
            Actor(id=owner.id, role=owner.role), "shop.register", tenant.id,
            telegram=bool(telegram_user_id),
        )
    )
    return RegisterShopResult(owner=owner, shop_slug=slug)


async def _unique_slug(uow: IUnitOfWork, shop_name: str) -> str:
    base = generate_slug(shop_name)
    candidate = base
    suffix = 2
    while await uow.tenants.get_by_slug(candidate) is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
