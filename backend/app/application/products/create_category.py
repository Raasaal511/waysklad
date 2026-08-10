from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.catalog.entities import Category
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class CreateCategoryCommand:
    name: str
    parent_id: int | None = None


class CreateCategoryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: CreateCategoryCommand) -> Category:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            category = Category(id=None, name=cmd.name, parent_id=cmd.parent_id)
            await uow.categories.add(category)
            await uow.audit.add(
                AuditEntry.record(actor, "category.create", None, name=category.name)
            )
            await uow.commit()
        return category
