from sqlalchemy import case, false, func, literal, or_, select

from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Category, Product
from app.domain.catalog.repository import (
    DuplicateLookupKey,
    DuplicateMatch,
    ICategoryRepository,
    IProductRepository,
    IUnitRepository,
)
from app.domain.common.exceptions import NotFoundError
from app.domain.common.quantity import Unit
from app.infrastructure.db.filtering.product_filter import ProductFilterFactory
from app.infrastructure.db.mappers.catalog import (
    CategoryMapper,
    ProductMapper,
    ProductVariantMapper,
    ServiceMapper,
    UnitMapper,
)
from app.infrastructure.db.models.catalog import (
    CategoryModel,
    ProductModel,
    ProductVariantModel,
    UnitModel,
)
from app.infrastructure.db.models.inventory import StockDocumentLineModel, StockItemModel
from app.infrastructure.db.models.orders import OrderLineModel
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel, SaleReturnLineModel, SaleReturnModel
from app.infrastructure.db.models.storefront import StorefrontRequestLineModel
from app.infrastructure.db.models.tasks import TaskModel
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

    async def save(self, category: Category) -> Category:
        model = (
            await self._session.execute(
                select(CategoryModel).where(
                    CategoryModel.tenant_id == self._tenant,
                    CategoryModel.id == category.id,
                )
            )
        ).scalar_one_or_none()
        if model is None:
            raise NotFoundError(f"Категория {category.id} не найдена")
        model.name = category.name
        model.parent_id = category.parent_id
        model.platform_category_id = category.platform_category_id
        await self._session.flush()
        return category

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
        model.compare_at_price = (
            product.compare_at_price.amount if product.compare_at_price is not None else None
        )
        model.min_stock = product.min_stock
        model.photo = product.photo
        model.description = product.description
        model.warranty_text = product.warranty_text
        model.storefront_photos = list(product.storefront_photos)
        model.show_on_storefront = product.show_on_storefront
        model.storefront_min_qty = product.storefront_min_qty
        model.storefront_step_qty = product.storefront_step_qty
        if product.service is None:
            model.service = None
        elif model.service is None:
            model.service = ServiceMapper.to_orm(product.service, self._tenant)
        else:
            model.service.duration_minutes = product.service.duration_minutes
            model.service.performer_id = product.service.performer_id
        # варианты: существующие обновляются, новые добавляются, убранные удаляются (delete-orphan)
        existing = {v.id: v for v in model.variants}
        updated = []
        for variant in product.variants:
            if variant.id is not None and variant.id in existing:
                variant_model = existing[variant.id]
                variant_model.size = variant.size
                variant_model.color = variant.color
                variant_model.barcode = variant.barcode.value if variant.barcode else None
                variant_model.photo = variant.photo
                variant_model.price = variant.price.amount if variant.price else None
                variant_model.name = variant.name
                variant_model.addon = variant.addon
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

    async def list_by_ids(self, product_ids: list[int]) -> list[Product]:
        # один запрос на весь список — иначе карточки заказов покупателя
        # дали бы по обращению на каждую позицию (N+1)
        if not product_ids:
            return []
        models = (
            (
                await self._session.execute(
                    select(ProductModel).where(
                        ProductModel.tenant_id == self._tenant,
                        ProductModel.id.in_(product_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        units = await self._units_map()
        return [ProductMapper.to_entity(m, units) for m in models]

    async def deactivate(self, product_id: int) -> None:
        model = await self._get_model(product_id)
        if model is None:
            raise NotFoundError(f"Товар {product_id} не найден")
        model.is_active = False
        await self._session.flush()

    async def delete(self, product_id: int) -> None:
        model = await self._get_model(product_id)
        if model is None:
            raise NotFoundError(f"Товар {product_id} не найден")
        await self._session.delete(model)
        await self._session.flush()

    async def has_activity(self, product_id: int) -> bool:
        checks = (
            select(SaleLineModel.id).where(
                SaleLineModel.tenant_id == self._tenant, SaleLineModel.product_id == product_id
            ),
            select(OrderLineModel.id).where(
                OrderLineModel.tenant_id == self._tenant, OrderLineModel.product_id == product_id
            ),
            select(StorefrontRequestLineModel.id).where(
                StorefrontRequestLineModel.tenant_id == self._tenant,
                StorefrontRequestLineModel.product_id == product_id,
            ),
            select(StockDocumentLineModel.id).where(
                StockDocumentLineModel.tenant_id == self._tenant,
                StockDocumentLineModel.product_id == product_id,
            ),
            select(TaskModel.id).where(
                TaskModel.tenant_id == self._tenant, TaskModel.product_id == product_id
            ),
        )
        for query in checks:
            if (await self._session.execute(query.limit(1))).first() is not None:
                return True
        return False

    def _search_filter(self, query: str, category_id: int | None = None):
        pattern = f"%{query}%"
        conditions = [
            ProductModel.tenant_id == self._tenant,
            ProductModel.is_active.is_(True),
            or_(
                ProductModel.name.ilike(pattern),
                ProductModel.sku.ilike(pattern),
                ProductModel.barcode.ilike(pattern),
            ),
        ]
        if category_id is not None:
            conditions.append(ProductModel.category_id == category_id)
        return conditions

    async def list_filtered(
        self,
        raw_params: dict,
        warehouse_id: int | None = None,
        warehouse_ids: list[int] | None = None,
        variant_size: str | None = None,
        variant_color: str | None = None,
    ) -> tuple[list[Product], int]:
        fields = ProductFilterFactory.build_fields(warehouse_id, warehouse_ids)
        variant_conditions = []
        if variant_size is not None:
            variant_conditions.append(ProductVariantModel.size == variant_size)
        if variant_color is not None:
            variant_conditions.append(ProductVariantModel.color == variant_color)
        # фильтр по варианту — не через generic-DSL (EQ/IN там не выражают
        # «есть хотя бы один вариант с size/color == X»), явный EXISTS точечно
        # для этого публичного кейса витрины
        variant_exists = (
            select(1)
            .where(ProductVariantModel.product_id == ProductModel.id, *variant_conditions)
            .exists()
            if variant_conditions
            else None
        )

        base = select(ProductModel).where(
            ProductModel.tenant_id == self._tenant, ProductModel.is_active.is_(True)
        )
        count_base = (
            select(func.count())
            .select_from(ProductModel)
            .where(ProductModel.tenant_id == self._tenant, ProductModel.is_active.is_(True))
        )
        if variant_exists is not None:
            base = base.where(variant_exists)
            count_base = count_base.where(variant_exists)

        models = await ProductFilterFactory.fetch_list(self._session, raw_params, base, fields)
        total = await ProductFilterFactory.fetch_count(self._session, raw_params, count_base, fields)
        units = await self._units_map()
        return [ProductMapper.to_entity(m, units) for m in models], total

    async def count_storefront_by_category(self) -> dict[int | None, int]:
        rows = (
            await self._session.execute(
                select(ProductModel.category_id, func.count())
                .where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.is_active.is_(True),
                    ProductModel.show_on_storefront.is_(True),
                )
                .group_by(ProductModel.category_id)
            )
        ).all()
        return {category_id: count for category_id, count in rows}

    async def count_storefront_by_kind(self) -> dict[str, int]:
        """Сколько товаров и сколько услуг на витрине — вкладка «Услуги»
        показывается покупателю, только когда услуги действительно есть."""
        rows = (
            await self._session.execute(
                select(ProductModel.kind, func.count())
                .where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.is_active.is_(True),
                    ProductModel.show_on_storefront.is_(True),
                )
                .group_by(ProductModel.kind)
            )
        ).all()
        return {kind: count for kind, count in rows}

    async def list_storefront_variant_options(self) -> tuple[list[str], list[str]]:
        base_filters = (
            ProductModel.tenant_id == self._tenant,
            ProductModel.is_active.is_(True),
            ProductModel.show_on_storefront.is_(True),
            ProductVariantModel.product_id == ProductModel.id,
        )
        sizes = (
            await self._session.execute(
                select(ProductVariantModel.size)
                .join(ProductModel)
                .where(*base_filters, ProductVariantModel.size != "")
                .distinct()
                .order_by(ProductVariantModel.size)
            )
        ).scalars().all()
        colors = (
            await self._session.execute(
                select(ProductVariantModel.color)
                .join(ProductModel)
                .where(*base_filters, ProductVariantModel.color != "")
                .distinct()
                .order_by(ProductVariantModel.color)
            )
        ).scalars().all()
        return list(sizes), list(colors)

    async def list_similar_in_shop(
        self,
        product_id: int,
        category_id: int | None,
        parent_category_id: int | None,
        warehouse_ids: list[int],
        limit: int,
    ) -> list[Product]:
        # приоритет группы: 0 — та же категория, 1 — та же родительская, 2 — остальные.
        # false() вместо пропуска ветки — category_id/parent_category_id может быть
        # None (товар без категории), тогда группа 0/1 просто никогда не совпадает.
        same_category = (
            ProductModel.category_id == category_id if category_id is not None else false()
        )
        same_parent = (
            CategoryModel.parent_id == parent_category_id
            if parent_category_id is not None
            else false()
        )
        priority = case((same_category, 0), (same_parent, 1), else_=2)
        stock_expr = (
            select(func.coalesce(func.sum(StockItemModel.quantity), 0))
            .where(
                StockItemModel.product_id == ProductModel.id,
                StockItemModel.warehouse_id.in_(warehouse_ids),
            )
            .correlate(ProductModel)
            .scalar_subquery()
            if warehouse_ids
            else literal(0)
        )
        returned = (
            select(func.coalesce(func.sum(SaleReturnLineModel.quantity), 0))
            .join(SaleReturnModel, SaleReturnModel.id == SaleReturnLineModel.return_id)
            .where(SaleReturnLineModel.sale_line_id == SaleLineModel.id)
            .correlate(SaleLineModel)
            .scalar_subquery()
        )
        sold_count_expr = (
            select(func.coalesce(func.sum(SaleLineModel.quantity - returned), 0))
            .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
            .where(
                SaleLineModel.product_id == ProductModel.id,
                SaleModel.tenant_id == self._tenant,
                SaleModel.deleted_at.is_(None),
            )
            .correlate(ProductModel)
            .scalar_subquery()
        )

        stmt = (
            select(ProductModel)
            .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
            .where(
                ProductModel.tenant_id == self._tenant,
                ProductModel.is_active.is_(True),
                ProductModel.show_on_storefront.is_(True),
                ProductModel.id != product_id,
            )
            .order_by(
                priority,
                (stock_expr > 0).desc(),
                sold_count_expr.desc(),
                ProductModel.id.desc(),
            )
            .limit(limit)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        units = await self._units_map()
        return [ProductMapper.to_entity(m, units) for m in models]

    async def search_all(self, query: str = "") -> list[Product]:
        models = (
            await self._session.execute(
                select(ProductModel).where(*self._search_filter(query)).order_by(ProductModel.name)
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

    async def find_duplicates(self, keys: list[DuplicateLookupKey]) -> list[DuplicateMatch]:
        if not keys:
            return []
        names = {k.name for k in keys if k.name}
        skus = {k.sku for k in keys if k.sku}
        barcodes = {k.barcode for k in keys if k.barcode}

        conditions = []
        if names:
            conditions.append(ProductModel.name.in_(names))
        if skus:
            conditions.append(ProductModel.sku.in_(skus))
        if barcodes:
            conditions.append(ProductModel.barcode.in_(barcodes))
        if not conditions:
            return []

        models = (
            await self._session.execute(
                select(ProductModel).where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.is_active.is_(True),
                    or_(*conditions),
                )
            )
        ).scalars().all()

        variant_models: list[ProductVariantModel] = []
        if barcodes:
            variant_models = (
                await self._session.execute(
                    select(ProductVariantModel)
                    .join(ProductModel, ProductModel.id == ProductVariantModel.product_id)
                    .where(
                        ProductVariantModel.tenant_id == self._tenant,
                        ProductModel.is_active.is_(True),
                        ProductVariantModel.barcode.in_(barcodes),
                    )
                )
            ).scalars().all()
            known_ids = {m.id for m in models}
            missing_ids = {vm.product_id for vm in variant_models} - known_ids
            if missing_ids:
                extra = (
                    await self._session.execute(
                        select(ProductModel).where(
                            ProductModel.id.in_(missing_ids),
                            ProductModel.tenant_id == self._tenant,
                        )
                    )
                ).scalars().all()
                models = [*models, *extra]

        by_name: dict[str, ProductModel] = {m.name: m for m in models}
        by_sku: dict[str, ProductModel] = {m.sku: m for m in models if m.sku}
        by_barcode: dict[str, ProductModel] = {m.barcode: m for m in models if m.barcode}
        models_by_id = {m.id: m for m in models}
        by_variant_barcode: dict[str, ProductModel] = {
            vm.barcode: models_by_id[vm.product_id]
            for vm in variant_models
            if vm.barcode and vm.product_id in models_by_id
        }

        units = await self._units_map()
        entity_cache: dict[int, Product] = {}

        def _entity(m: ProductModel) -> Product:
            if m.id not in entity_cache:
                entity_cache[m.id] = ProductMapper.to_entity(m, units)
            return entity_cache[m.id]

        results: list[DuplicateMatch] = []
        for key in keys:
            if key.barcode:
                m = by_barcode.get(key.barcode) or by_variant_barcode.get(key.barcode)
                if m is not None:
                    results.append(DuplicateMatch(key.row_index, _entity(m), "barcode"))
            if key.sku and key.sku in by_sku:
                results.append(DuplicateMatch(key.row_index, _entity(by_sku[key.sku]), "sku"))
            if key.name and key.name in by_name:
                results.append(DuplicateMatch(key.row_index, _entity(by_name[key.name]), "name"))
        return results

    async def _get_model(self, product_id: int) -> ProductModel | None:
        return (
            await self._session.execute(
                select(ProductModel).where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.id == product_id,
                )
            )
        ).scalar_one_or_none()
