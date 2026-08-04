from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.common.slug import generate_slug
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, Tenant, User, Warehouse
from app.domain.identity.permissions import Actor
from app.domain.identity.ports import IPasswordHasher


@dataclass(frozen=True)
class RegisterShopCommand:
    shop_name: str
    owner_name: str
    phone: str
    password: str


@dataclass(frozen=True)
class RegisterShopResult:
    owner: User
    shop_slug: str


class RegisterShopUseCase:
    def __init__(self, uow: IUnitOfWork, hasher: IPasswordHasher):
        self._uow = uow
        self._hasher = hasher

    async def execute(self, cmd: RegisterShopCommand) -> RegisterShopResult:
        if len(cmd.password) < 6:
            raise DomainError("Пароль должен быть не короче 6 символов")
        phone = Phone(cmd.phone)

        async with self._uow as uow:
            if await uow.users.get_by_phone(str(phone)) is not None:
                raise DomainError("Этот телефон уже зарегистрирован")

            slug = await self._unique_slug(uow, cmd.shop_name)
            tenant = await uow.tenants.add(Tenant(id=None, name=cmd.shop_name, slug=slug))
            uow.tenant_id = tenant.id

            owner = await uow.users.add(
                User(
                    id=None,
                    name=cmd.owner_name,
                    phone=phone,
                    role=Role.OWNER,
                    password_hash=self._hasher.hash(cmd.password),
                )
            )
            await uow.warehouses.add(Warehouse(id=None, name="Основной склад"))
            await uow.audit.add(
                AuditEntry.record(
                    Actor(id=owner.id, role=owner.role), "shop.register", tenant.id
                )
            )
            await uow.commit()
            return RegisterShopResult(owner=owner, shop_slug=slug)

    @staticmethod
    async def _unique_slug(uow: IUnitOfWork, shop_name: str) -> str:
        base = generate_slug(shop_name)
        candidate = base
        suffix = 2
        while await uow.tenants.get_by_slug(candidate) is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate
