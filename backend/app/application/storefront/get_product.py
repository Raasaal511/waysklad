from dataclasses import dataclass

from app.domain.catalog.entities import Product
from app.domain.common.exceptions import NotFoundError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class GetStorefrontProductCommand:
    slug: str
    product_id: int


@dataclass(frozen=True)
class StorefrontProductResult:
    shop_name: str
    product: Product
    in_stock: bool


class GetStorefrontProductUseCase:
    """Карточка одного товара на публичной витрине — для отдельной ссылки,
    например «скинуть этот товар клиенту в WhatsApp»."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: GetStorefrontProductCommand) -> StorefrontProductResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            try:
                product = await uow.products.get(cmd.product_id)
            except NotFoundError:
                return None
            if not product.show_on_storefront:
                return None
            stock_items = await uow.stock.list_all()

        in_stock = any(
            item.product_id == product.id and item.quantity > 0 for item in stock_items
        )
        return StorefrontProductResult(shop_name=tenant.name, product=product, in_stock=in_stock)
