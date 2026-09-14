from dataclasses import dataclass

from app.domain.catalog.description_generator import IDescriptionGenerator
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require


@dataclass(frozen=True)
class GenerateProductDescriptionCommand:
    product_id: int


@dataclass(frozen=True)
class GenerateProductDescriptionResult:
    description: str


class GenerateProductDescriptionUseCase:
    """Только предлагает текст для предпросмотра — ничего не сохраняет.
    Владелец правит предложенный текст и сохраняет обычным PUT /products/{id}."""

    def __init__(self, uow: IUnitOfWork, generator: IDescriptionGenerator):
        self._uow = uow
        self._generator = generator

    async def execute(
        self, actor: Actor, cmd: GenerateProductDescriptionCommand
    ) -> GenerateProductDescriptionResult:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            product = await uow.products.get(cmd.product_id)
            category_name = ""
            if product.category_id is not None:
                category = await uow.categories.get(product.category_id)
                category_name = category.name

        description = await self._generator.generate(product.name, category_name)
        return GenerateProductDescriptionResult(description=description)
