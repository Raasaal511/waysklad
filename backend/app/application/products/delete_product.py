from dataclasses import dataclass

from app.domain.audit.entities import AuditEntry
from app.domain.common.cache import ICache
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.infrastructure.cache.cache_aside import invalidate_shop_cache


@dataclass(frozen=True)
class DeleteProductCommand:
    product_id: int


class DeleteProductUseCase:
    """Удаление товара: если он нигде не фигурировал (нет продаж, заказов,
    заявок с витрины, складских документов, задач) — удаляется физически.
    Иначе — soft-delete (is_active=False), чтобы не потерять историю, на
    которую ссылается product_id."""

    def __init__(self, uow: IUnitOfWork, cache: ICache | None = None):
        self._uow = uow
        self._cache = cache

    async def execute(self, actor: Actor, cmd: DeleteProductCommand) -> None:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            has_activity = await uow.products.has_activity(product.id)
            if has_activity:
                await uow.products.deactivate(product.id)
                action = "product.delete"
            else:
                await uow.products.delete(product.id)
                action = "product.delete_permanent"
            await uow.audit.add(AuditEntry.record(actor, action, product.id, name=product.name))
            await uow.commit()
            await invalidate_shop_cache(self._cache, uow)
