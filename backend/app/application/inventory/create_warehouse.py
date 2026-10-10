from dataclasses import dataclass, field

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


_ASSIGNABLE_ROLES = (Role.MANAGER, Role.SELLER, Role.STOREKEEPER)


@dataclass(frozen=True)
class CreateWarehouseCommand:
    name: str
    address: str = ""
    # id сотрудников (manager/seller/storekeeper), назначаемых на этот склад
    assigned_user_ids: list[int] = field(default_factory=list)
    # по умолчанию склад виден витрине: иначе его остатки не попадают в
    # in_stock_product_ids (get_catalog.py) и все товары магазина показываются
    # как «нет в наличии», хотя остаток есть. Скрытый склад — редкий случай,
    # он выключается осознанно в карточке склада.
    show_on_storefront: bool = True


class CreateWarehouseUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: CreateWarehouseCommand) -> Warehouse:
        require(actor, Permission.WAREHOUSES_MANAGE)

        async with self._uow as uow:
            for user_id in cmd.assigned_user_ids:
                candidate = await uow.users.get(user_id)
                if candidate.role not in _ASSIGNABLE_ROLES:
                    raise DomainError(
                        f"«{candidate.name}» не может быть привязан к складу — "
                        "нужна роль управляющего, продавца или кладовщика"
                    )

            warehouse = await uow.warehouses.add(
                Warehouse(
                    id=None,
                    name=cmd.name,
                    address=cmd.address,
                    assigned_user_ids=cmd.assigned_user_ids,
                    show_on_storefront=cmd.show_on_storefront,
                )
            )
            await uow.audit.add(
                AuditEntry.record(
                    actor, "warehouse.create", warehouse.id,
                    name=warehouse.name, assigned_user_ids=cmd.assigned_user_ids,
                )
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
            return warehouse
