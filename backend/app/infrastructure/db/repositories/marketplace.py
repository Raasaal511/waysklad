from decimal import Decimal

from sqlalchemy import false, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.marketplace.repository import IMarketplaceProductRepository, MarketplaceProductRow
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.db.models.catalog import CategoryModel, ProductModel, ProductVariantModel
from app.infrastructure.db.models.identity import TenantModel, WarehouseModel
from app.infrastructure.db.models.inventory import StockItemModel
from app.infrastructure.db.models.reviews import ReviewModel
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel, SaleReturnLineModel, SaleReturnModel

_SORT_COLUMNS = {
    "name": ProductModel.name.asc(),
    "price_asc": ProductModel.retail_price.asc(),
    "price_desc": ProductModel.retail_price.desc(),
    "created_desc": ProductModel.created_at.desc(),
}


def _stock_expr(warehouse_ids: list[int]):
    return (
        select(func.coalesce(func.sum(StockItemModel.quantity), 0))
        .where(
            StockItemModel.product_id == ProductModel.id,
            StockItemModel.warehouse_id.in_(warehouse_ids),
        )
        .correlate(ProductModel)
        .scalar_subquery()
    )


def _rating_expr():
    """Средний рейтинг по видимым отзывам — NULL при их отсутствии (не 0),
    тот же смысл, что у ProductFilterFactory._rating_expr для storefront."""
    return (
        select(func.avg(ReviewModel.rating))
        .where(
            ReviewModel.product_id == ProductModel.id,
            ReviewModel.is_hidden.is_(False),
        )
        .correlate(ProductModel)
        .scalar_subquery()
    )


class SqlAlchemyMarketplaceProductRepository(IMarketplaceProductRepository):
    """Не наследует SqlAlchemyRepository: тот привязан к одному tenant_id за раз
    (см. SqlAlchemyRepository._tenant), а общий каталог платформы принципиально
    читает товары сразу многих магазинов одним запросом — конструктор берёт сессию напрямую."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_visible_warehouse_ids(self, tenant_ids: list[int]) -> list[int]:
        if not tenant_ids:
            return []
        rows = (
            await self._session.execute(
                select(WarehouseModel.id).where(
                    WarehouseModel.tenant_id.in_(tenant_ids),
                    WarehouseModel.show_on_storefront.is_(True),
                )
            )
        ).scalars().all()
        return list(rows)

    async def list_products(
        self,
        visible_tenant_ids,
        warehouse_ids,
        query: str = "",
        category: str | None = None,
        price_min=None,
        price_max=None,
        in_stock_only: bool = False,
        variant_size: str | None = None,
        variant_color: str | None = None,
        shop_slug: str | None = None,
        sort: str = "name",
        limit: int = 50,
        offset: int = 0,
        min_rating: int | None = None,
    ) -> tuple[list[MarketplaceProductRow], int]:
        if not visible_tenant_ids:
            return [], 0

        stock_expr = _stock_expr(warehouse_ids) if warehouse_ids else None

        conditions = [
            ProductModel.tenant_id.in_(visible_tenant_ids),
            ProductModel.is_active.is_(True),
            ProductModel.show_on_storefront.is_(True),
        ]
        if shop_slug is not None:
            conditions.append(TenantModel.slug == shop_slug)
        if query.strip():
            pattern = f"%{query.strip()}%"
            conditions.append(
                or_(
                    ProductModel.name.ilike(pattern),
                    ProductModel.sku.ilike(pattern),
                    ProductModel.barcode.ilike(pattern),
                )
            )
        if category is not None:
            conditions.append(CategoryModel.name == category)
        if price_min is not None:
            conditions.append(ProductModel.retail_price >= price_min)
        if price_max is not None:
            conditions.append(ProductModel.retail_price <= price_max)
        if in_stock_only:
            if stock_expr is None:
                # нет ни одного видимого склада — наличие всегда 0, фильтр даёт пустой результат
                conditions.append(false())
            else:
                conditions.append(stock_expr > 0)
        if min_rating is not None:
            # NULL (нет отзывов) не проходит GTE-сравнение в SQL — тот же
            # смысл, что и у storefront-эквивалента этого фильтра
            conditions.append(_rating_expr() >= min_rating)

        variant_conditions = []
        if variant_size is not None:
            variant_conditions.append(ProductVariantModel.size == variant_size)
        if variant_color is not None:
            variant_conditions.append(ProductVariantModel.color == variant_color)
        if variant_conditions:
            variant_exists = (
                select(1)
                .where(ProductVariantModel.product_id == ProductModel.id, *variant_conditions)
                .exists()
            )
            conditions.append(variant_exists)

        stock_col = (
            func.coalesce(stock_expr, 0) if stock_expr is not None else literal(0)
        ).label("stock")

        base = (
            select(ProductModel, TenantModel, CategoryModel, stock_col)
            .join(TenantModel, TenantModel.id == ProductModel.tenant_id)
            .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
            .where(*conditions)
        )

        count_stmt = (
            select(func.count())
            .select_from(ProductModel)
            .join(TenantModel, TenantModel.id == ProductModel.tenant_id)
            .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
            .where(*conditions)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        order_col = _SORT_COLUMNS.get(sort, _SORT_COLUMNS["name"])
        stmt = base.order_by(order_col).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).all()

        product_ids = [product.id for product, _, _, _ in rows]
        sold_counts = await self.sold_count_by_products(product_ids)
        ratings = await self.rating_by_products(product_ids)
        _empty_rating = ProductRatingAggregate(average_rating=0.0, reviews_count=0)

        products: list[MarketplaceProductRow] = [
            MarketplaceProductRow(
                product_id=product.id,
                name=product.name,
                retail_price=product.retail_price,
                photo=product.photo,
                category_name=category_model.name if category_model else None,
                in_stock=stock > 0,
                min_order_qty=product.storefront_min_qty,
                order_step_qty=product.storefront_step_qty,
                shop_slug=tenant.slug or "",
                shop_name=tenant.name,
                sku=product.sku or "",
                sold_count=sold_counts.get(product.id, Decimal("0")),
                rating=ratings.get(product.id, _empty_rating),
            )
            for product, tenant, category_model, stock in rows
        ]
        return products, total

    async def sold_count_by_products(self, product_ids: list[int]) -> dict[int, Decimal]:
        if not product_ids:
            return {}
        returned = (
            select(
                SaleReturnLineModel.sale_line_id.label("sale_line_id"),
                func.sum(SaleReturnLineModel.quantity).label("returned_qty"),
            )
            .join(SaleReturnModel, SaleReturnModel.id == SaleReturnLineModel.return_id)
            .group_by(SaleReturnLineModel.sale_line_id)
            .subquery()
        )
        effective_qty = SaleLineModel.quantity - func.coalesce(returned.c.returned_qty, 0)
        rows = (
            await self._session.execute(
                select(SaleLineModel.product_id, func.sum(effective_qty))
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(
                    SaleModel.deleted_at.is_(None),
                    SaleLineModel.product_id.in_(product_ids),
                )
                .group_by(SaleLineModel.product_id)
            )
        ).all()
        return {pid: quantity for pid, quantity in rows}

    async def rating_by_products(
        self, product_ids: list[int]
    ) -> dict[int, ProductRatingAggregate]:
        if not product_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    ReviewModel.product_id,
                    func.avg(ReviewModel.rating),
                    func.count(ReviewModel.id),
                )
                .where(
                    ReviewModel.product_id.in_(product_ids),
                    ReviewModel.is_hidden.is_(False),
                )
                .group_by(ReviewModel.product_id)
            )
        ).all()
        return {
            product_id: ProductRatingAggregate(average_rating=float(avg), reviews_count=count)
            for product_id, avg, count in rows
        }
