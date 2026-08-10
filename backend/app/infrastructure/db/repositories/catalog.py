from sqlalchemy import or_, select

from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Category, Product
from app.domain.catalog.repository import ICategoryRepository, IProductRepository, IUnitRepository
from app.domain.common.exceptions import NotFoundError
from app.domain.common.quantity import Unit
from app.infrastructure.db.mappers.catalog import (
    CategoryMapper,
    ProductMapper,
    ProductVariantMapper,
    UnitMapper,
)
from app.infrastructure.db.models.catalog import (
    CategoryModel,
    ProductModel,
    ProductVariantModel,
    UnitModel,
)
from app.infrastructure.db.repositories.base import SqlAlchemyRepository


class SqlAlchemyCategoryRepository(SqlAlchemyRepository, ICategoryRepository):
    async def add(self, category: Category) -> Category:
        model = CategoryMapper.to_orm(category, self._tenant)
        self._session.add(model)
        await self._session.flush()
        category.id = model.id
        return category

    async def get(self, category_id: int) -> Category:
        model = (
            await self._session.execute(
                select(CategoryModel).where(
                    CategoryModel.tenant_id == self._tenant,
                    CategoryModel.id == category_id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Категория {category_id} не найдена")
        return CategoryMapper.to_entity(model)

    async def list(self) -> list[Category]:
        models = (
            await self._session.execute(
                select(CategoryModel)
                .where(CategoryModel.tenant_id == self._tenant)
                .order_by(CategoryModel.name)
            )
        ).scalars()
        return [CategoryMapper.to_entity(m) for m in models]


class SqlAlchemyUnitRepository(SqlAlchemyRepository, IUnitRepository):
    async def add(self, unit: Unit) -> Unit:
        self._session.add(UnitMapper.to_orm(unit, self._tenant))
        await self._session.flush()
        return unit

    async def get(self, code: str) -> Unit | None:
        model = (
            await self._session.execute(
                select(UnitModel).where(
                    UnitModel.tenant_id == self._tenant, UnitModel.code == code
                )
            )
        ).scalar_one_or_none()
        return UnitMapper.to_entity(model) if model else None

    async def list(self) -> list[Unit]:
        models = (
            await self._session.execute(
                select(UnitModel)
                .where(UnitModel.tenant_id == self._tenant)
                .order_by(UnitModel.code)
            )
        ).scalars()
        return [UnitMapper.to_entity(m) for m in models]


class SqlAlchemyProductRepository(SqlAlchemyRepository, IProductRepository):
    async def add(self, product: Product) -> Product:
        model = ProductMapper.to_orm(product, self._tenant)
        self._session.add(model)
        await self._session.flush()
        product.id = model.id
        for entity, variant_model in zip(product.variants, model.variants):
            entity.id = variant_model.id
        return product

    async def save(self, product: Product) -> Product:
        model = await self._get_model(product.id)
        if model is None:
            raise NotFoundError(f"Товар {product.id} не найден")
        model.name = product.name
        model.sku = product.sku or None
        model.barcode = product.barcode.value if product.barcode else None
        model.category_id = product.category_id
        model.unit_code = product.unit.code
        model.purchase_price = product.purchase_price.amount
        model.retail_price = product.retail_price.amount
        model.min_stock = product.min_stock
        model.photo = product.photo
        # варианты: существующие обновляются, новые добавляются, убранные удаляются (delete-orphan)
        existing = {v.id: v for v in model.variants}
        updated = []
        for variant in product.variants:
            if variant.id is not None and variant.id in existing:
                variant_model = existing[variant.id]
                variant_model.size = variant.size
                variant_model.color = variant.color
                variant_model.barcode = variant.barcode.value if variant.barcode else None
                updated.append(variant_model)
            else:
                updated.append(ProductVariantMapper.to_orm(variant, self._tenant))
        model.variants = updated
        await self._session.flush()
        for entity, variant_model in zip(product.variants, model.variants):
            entity.id = variant_model.id
        return product

    async def get(self, product_id: int) -> Product:
        model = await self._get_model(product_id)
        if model is None:
            raise NotFoundError(f"Товар {product_id} не найден")
        return ProductMapper.to_entity(model, await self._units_map())

    async def search(self, query: str) -> list[Product]:
        pattern = f"%{query}%"
        models = (
            await self._session.execute(
                select(ProductModel)
                .where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.is_active.is_(True),
                    or_(ProductModel.name.ilike(pattern), ProductModel.sku.ilike(pattern)),
                )
                .order_by(ProductModel.name)
                .limit(50)
            )
        ).scalars().all()
        units = await self._units_map()
        return [ProductMapper.to_entity(m, units) for m in models]

    async def get_by_barcode(self, barcode: Barcode) -> Product | None:
        model = (
            await self._session.execute(
                select(ProductModel).where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.barcode == barcode.value,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            # штрихкод может принадлежать варианту (размеру/цвету)
            variant = (
                await self._session.execute(
                    select(ProductVariantModel).where(
                        ProductVariantModel.tenant_id == self._tenant,
                        ProductVariantModel.barcode == barcode.value,
                    )
                )
            ).scalar_one_or_none()
            if variant is None:
                return None
            model = await self._get_model(variant.product_id)
            if model is None:
                return None
        return ProductMapper.to_entity(model, await self._units_map())

    async def _get_model(self, product_id: int) -> ProductModel | None:
        return (
            await self._session.execute(
                select(ProductModel).where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.id == product_id,
                )
            )
        ).scalar_one_or_none()
