from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Category
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class UpdateCategoryCommand:
    category_id: int
    name: str
    parent_id: int | None = None
    platform_category_id: int | None = None


class UpdateCategoryUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: UpdateCategoryCommand) -> Category:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            category = Category(
                id=cmd.category_id,
                name=cmd.name,
                parent_id=cmd.parent_id,
                platform_category_id=cmd.platform_category_id,
            )
            category = await uow.categories.save(category)
            await uow.audit.add(
                AuditEntry.record(actor, "category.update", category.id, name=category.name)
            )
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
        return category
