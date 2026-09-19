from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, false, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.marketplace.repository import (
    IMarketplaceProductRepository,
    MarketplaceProductRow,
    ShopChip,
    SuggestProductRow,
)
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.db.models.catalog import CategoryModel, ProductModel, ProductVariantModel
from app.infrastructure.db.models.identity import TenantModel, WarehouseModel
from app.infrastructure.db.models.inventory import StockItemModel
from app.infrastructure.db.models.reviews import ReviewModel
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel, SaleReturnLineModel, SaleReturnModel

_NEW_WINDOW_DAYS = 14
_HIT_WINDOW_DAYS = 30
_HIT_MIN_SALES = 5
_HIT_TOP_FRACTION = Decimal("0.1")  # топ-10%

_STATIC_SORT_COLUMNS = {
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


def _reviews_count_expr():
    return (
        select(func.count(ReviewModel.id))
        .where(
            ReviewModel.product_id == ProductModel.id,
            ReviewModel.is_hidden.is_(False),
        )
        .correlate(ProductModel)
        .scalar_subquery()
    )


def _discount_percent_expr():
    """int(floor((old-retail)/old*100)), NULL при отсутствии старой цены/скидки
    или когда скидка меньше 3% — та же формула и тот же порог, что
    Product.discount_percent в домене (иначе with_discount=true/sort=discount
    расходились бы с тем, что реально показывается в ответе)."""
    old = ProductModel.compare_at_price
    percent = func.floor((old - ProductModel.retail_price) / old * 100)
    return case(
        (old.is_not(None) & (old > ProductModel.retail_price) & (percent >= 3), percent),
        else_=None,
    )


def _sold_count_since_expr(since: datetime):
    """Продано (за вычетом возвратов) с указанной даты — коррелированный
    скаляр для сортировки sort=popular без отдельного batch-запроса на странице."""
    returned = (
        select(func.coalesce(func.sum(SaleReturnLineModel.quantity), 0))
        .join(SaleReturnModel, SaleReturnModel.id == SaleReturnLineModel.return_id)
        .where(SaleReturnLineModel.sale_line_id == SaleLineModel.id)
        .correlate(SaleLineModel)
        .scalar_subquery()
    )
    effective_qty = SaleLineModel.quantity - returned
    return (
        select(func.coalesce(func.sum(effective_qty), 0))
        .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
        .where(
            SaleLineModel.product_id == ProductModel.id,
            SaleModel.deleted_at.is_(None),
            SaleModel.created_at >= since,
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

    async def find_tenant_by_product(self, product_id: int) -> int | None:
        return (
            await self._session.execute(
                select(ProductModel.tenant_id).where(ProductModel.id == product_id)
            )
        ).scalar_one_or_none()

    async def get_created_at(self, product_id: int) -> datetime | None:
        return (
            await self._session.execute(
                select(ProductModel.created_at).where(ProductModel.id == product_id)
            )
        ).scalar_one_or_none()

    async def list_products(
        self,
        visible_tenant_ids,
        warehouse_ids,
        query: str = "",
        category: str | None = None,
        platform_category_ids: list[int] | None = None,
        city: str | None = None,
        price_min=None,
        price_max=None,
        in_stock_only: bool = False,
        with_discount: bool = False,
        variant_size: str | None = None,
        variant_color: str | None = None,
        shop_slug: str | None = None,
        sort: str = "name",
        limit: int = 50,
        offset: int = 0,
        min_rating: int | None = None,
        hit_product_ids: frozenset[int] = frozenset(),
        skip_count: bool = False,
        sold_counts: dict[int, Decimal] | None = None,
        ratings: dict[int, ProductRatingAggregate] | None = None,
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
        if platform_category_ids is not None:
            conditions.append(CategoryModel.platform_category_id.in_(platform_category_ids))
        if city is not None:
            conditions.append(TenantModel.city == city)
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
        if with_discount:
            conditions.append(_discount_percent_expr().is_not(None))
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

        if skip_count:
            total = -1  # вызывающему total не нужен (см. docstring в протоколе) — не считаем
        else:
            count_stmt = (
                select(func.count())
                .select_from(ProductModel)
                .join(TenantModel, TenantModel.id == ProductModel.tenant_id)
                .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
                .where(*conditions)
            )
            total = (await self._session.execute(count_stmt)).scalar_one()

        if sort == "popular":
            since = datetime.now(timezone.utc) - timedelta(days=_HIT_WINDOW_DAYS)
            order_col = _sold_count_since_expr(since).desc()
        elif sort == "rating":
            # NULLS LAST — товары без отзывов уходят в конец, не в начало
            order_col = (_rating_expr().desc().nullslast(), _reviews_count_expr().desc())
        elif sort == "discount":
            order_col = _discount_percent_expr().desc().nullslast()
        else:
            order_col = _STATIC_SORT_COLUMNS.get(sort, _STATIC_SORT_COLUMNS["name"])

        order_cols = order_col if isinstance(order_col, tuple) else (order_col,)
        stmt = base.order_by(*order_cols).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).all()

        product_ids = [product.id for product, _, _, _ in rows]
        if sold_counts is None:
            sold_counts = await self.sold_count_by_products(product_ids)
        if ratings is None:
            ratings = await self.rating_by_products(product_ids)
        _empty_rating = ProductRatingAggregate(average_rating=0.0, reviews_count=0)
        new_cutoff = datetime.now(timezone.utc) - timedelta(days=_NEW_WINDOW_DAYS)

        def _row(product, tenant, category_model, stock) -> MarketplaceProductRow:
            discount_percent = _compute_discount_percent(product.retail_price, product.compare_at_price)
            return MarketplaceProductRow(
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
                shop_logo=tenant.logo,
                shop_is_verified=tenant.is_verified,
                shop_city=tenant.city,
                # old_price и discount_percent всегда null/не-null вместе —
                # скидка < 3% не показывается вообще (см. домен Product.old_price)
                old_price=product.compare_at_price if discount_percent is not None else None,
                discount_percent=discount_percent,
                is_new=_as_utc(product.created_at) >= new_cutoff,
                is_hit=product.id in hit_product_ids,
            )

        products: list[MarketplaceProductRow] = [_row(*row) for row in rows]
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

    async def compute_hit_product_ids(self, visible_tenant_ids: list[int]) -> frozenset[int]:
        if not visible_tenant_ids:
            return frozenset()
        since = datetime.now(timezone.utc) - timedelta(days=_HIT_WINDOW_DAYS)
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
                select(SaleLineModel.product_id, func.sum(effective_qty).label("qty"))
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(ProductModel, ProductModel.id == SaleLineModel.product_id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(
                    SaleModel.deleted_at.is_(None),
                    SaleModel.created_at >= since,
                    SaleModel.tenant_id.in_(visible_tenant_ids),
                    ProductModel.is_active.is_(True),
                    ProductModel.show_on_storefront.is_(True),
                )
                .group_by(SaleLineModel.product_id)
                .having(func.sum(effective_qty) >= _HIT_MIN_SALES)
                .order_by(func.sum(effective_qty).desc())
            )
        ).all()
        if not rows:
            return frozenset()
        top_n = max(1, int(len(rows) * _HIT_TOP_FRACTION))
        return frozenset(product_id for product_id, _qty in rows[:top_n])

    async def count_by_platform_category(
        self, visible_tenant_ids: list[int], city: str | None = None
    ) -> dict[int, int]:
        if not visible_tenant_ids:
            return {}
        conditions = [
            ProductModel.tenant_id.in_(visible_tenant_ids),
            ProductModel.is_active.is_(True),
            ProductModel.show_on_storefront.is_(True),
            CategoryModel.platform_category_id.is_not(None),
        ]
        stmt = (
            select(CategoryModel.platform_category_id, func.count(ProductModel.id))
            .select_from(ProductModel)
            .join(CategoryModel, CategoryModel.id == ProductModel.category_id)
        )
        if city is not None:
            stmt = stmt.join(TenantModel, TenantModel.id == ProductModel.tenant_id)
            conditions.append(TenantModel.city == city)
        stmt = stmt.where(*conditions).group_by(CategoryModel.platform_category_id)
        rows = (await self._session.execute(stmt)).all()
        return {platform_category_id: count for platform_category_id, count in rows}

    async def list_cities(self, visible_tenant_ids: list[int]) -> dict[str, int]:
        if not visible_tenant_ids:
            return {}
        rows = (
            await self._session.execute(
                select(TenantModel.city, func.count(TenantModel.id))
                .where(
                    TenantModel.id.in_(visible_tenant_ids),
                    TenantModel.city.is_not(None),
                )
                .group_by(TenantModel.city)
            )
        ).all()
        return {city: count for city, count in rows}

    async def list_shop_chips(
        self,
        visible_tenant_ids: list[int],
        city: str | None = None,
        query: str = "",
        sort: str = "popular",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ShopChip], int]:
        if not visible_tenant_ids:
            return [], 0

        visible_products = (
            select(ProductModel.tenant_id, func.count(ProductModel.id).label("products_count"))
            .where(
                ProductModel.tenant_id.in_(visible_tenant_ids),
                ProductModel.is_active.is_(True),
                ProductModel.show_on_storefront.is_(True),
            )
            .group_by(ProductModel.tenant_id)
            .subquery()
        )
        # магазины без единого видимого товара на витрине не считаются
        # магазинами маркетплейса (см. промпт M-B2 п.2) — INNER JOIN отсекает их сразу
        conditions = [TenantModel.id == visible_products.c.tenant_id]
        if city is not None:
            conditions.append(TenantModel.city == city)
        if query.strip():
            conditions.append(TenantModel.name.ilike(f"%{query.strip()}%"))

        since = datetime.now(timezone.utc) - timedelta(days=_HIT_WINDOW_DAYS)
        sold_expr = (
            select(func.coalesce(func.sum(SaleLineModel.quantity), 0))
            .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
            .where(
                SaleModel.tenant_id == TenantModel.id,
                SaleModel.deleted_at.is_(None),
                SaleModel.created_at >= since,
            )
            .correlate(TenantModel)
            .scalar_subquery()
        )
        rating_expr = (
            select(func.avg(ReviewModel.rating))
            .where(ReviewModel.tenant_id == TenantModel.id, ReviewModel.is_hidden.is_(False))
            .correlate(TenantModel)
            .scalar_subquery()
        )
        reviews_count_expr = (
            select(func.count(ReviewModel.id))
            .where(ReviewModel.tenant_id == TenantModel.id, ReviewModel.is_hidden.is_(False))
            .correlate(TenantModel)
            .scalar_subquery()
        )

        # count(*) over() — общее число подходящих магазинов в той же строке,
        # без отдельного COUNT(*)-запроса (см. промпт M-B2 п.2 — тест на
        # число SQL-запросов у GET /marketplace/home, использующего эту функцию)
        total_expr = func.count().over().label("total")

        base = (
            select(
                TenantModel,
                visible_products.c.products_count,
                func.coalesce(sold_expr, 0).label("sold_count_30d"),
                rating_expr.label("average_rating"),
                func.coalesce(reviews_count_expr, 0).label("reviews_count"),
                total_expr,
            )
            .join(visible_products, visible_products.c.tenant_id == TenantModel.id)
            .where(*conditions)
        )

        if sort == "rating":
            order_cols = (rating_expr.desc().nullslast(), reviews_count_expr.desc())
        elif sort == "new":
            order_cols = (TenantModel.created_at.desc(),)
        else:  # popular (по умолчанию)
            order_cols = (func.coalesce(sold_expr, 0).desc(),)

        stmt = base.order_by(*order_cols).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).all()

        total = rows[0].total if rows else 0
        chips = [
            ShopChip(
                slug=tenant.slug or "",
                name=tenant.name,
                logo=tenant.logo,
                city=tenant.city,
                is_verified=tenant.is_verified,
                average_rating=float(average_rating) if average_rating is not None else 0.0,
                reviews_count=reviews_count,
                products_count=products_count,
                sold_count_30d=Decimal(sold_count_30d),
            )
            for tenant, products_count, sold_count_30d, average_rating, reviews_count, _total in rows
        ]
        return chips, total

    async def suggest_products(
        self, visible_tenant_ids: list[int], query: str, city: str | None, limit: int = 5
    ) -> list[SuggestProductRow]:
        if not visible_tenant_ids or not query.strip():
            return []
        pattern = f"%{query.strip()}%"
        conditions = [
            ProductModel.tenant_id.in_(visible_tenant_ids),
            ProductModel.is_active.is_(True),
            ProductModel.show_on_storefront.is_(True),
            or_(ProductModel.name.ilike(pattern), ProductModel.sku.ilike(pattern)),
        ]
        stmt = (
            select(ProductModel.id, ProductModel.name, ProductModel.photo,
                   ProductModel.retail_price, TenantModel.slug)
            .join(TenantModel, TenantModel.id == ProductModel.tenant_id)
            .where(*conditions)
        )
        if city is not None:
            stmt = stmt.where(TenantModel.city == city)
        # по имени — самые точные совпадения (начинающиеся с запроса) первыми
        stmt = stmt.order_by(
            case((ProductModel.name.ilike(f"{query.strip()}%"), 0), else_=1), ProductModel.name
        ).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        return [
            SuggestProductRow(
                product_id=product_id, name=name, photo=photo,
                retail_price=retail_price, shop_slug=shop_slug or "",
            )
            for product_id, name, photo, retail_price, shop_slug in rows
        ]

    async def platform_stats(self, visible_tenant_ids: list[int]) -> tuple[int, int]:
        """(products_count, cities_count) — один запрос с двумя скалярными
        подзапросами вместо двух отдельных SELECT (см. промпт M-B2 п.2: тест
        на число SQL-запросов у GET /marketplace/home)."""
        if not visible_tenant_ids:
            return 0, 0
        products_count_expr = (
            select(func.count(ProductModel.id))
            .where(
                ProductModel.tenant_id.in_(visible_tenant_ids),
                ProductModel.is_active.is_(True),
                ProductModel.show_on_storefront.is_(True),
            )
            .scalar_subquery()
        )
        cities_count_expr = (
            select(func.count(func.distinct(TenantModel.city)))
            .where(TenantModel.id.in_(visible_tenant_ids), TenantModel.city.is_not(None))
            .scalar_subquery()
        )
        row = (
            await self._session.execute(select(products_count_expr, cities_count_expr))
        ).one()
        return row[0], row[1]

    async def _pg_trgm_available(self) -> bool:
        # Проверяем каждый раз, а не кешируем в процессе — расширение либо есть,
        # либо нет, запрос к pg_extension дешёвый (одна строка), а на managed
        # Postgres без прав миграция (см. 2026-09-19_pg_trgm_extension.py) просто
        # не создаёт расширение, и мы должны это увидеть без рестарта процесса.
        row = (
            await self._session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            )
        ).first()
        return row is not None

    async def list_similar_cross_shop(
        self,
        visible_tenant_ids: list[int],
        warehouse_ids: list[int],
        exclude_product_id: int,
        exclude_tenant_id: int,
        category_name: str | None,
        name_words: list[str],
        limit: int,
    ) -> list[MarketplaceProductRow]:
        other_tenant_ids = [t for t in visible_tenant_ids if t != exclude_tenant_id]
        if not other_tenant_ids:
            return []

        base_conditions = [
            ProductModel.tenant_id.in_(other_tenant_ids),
            ProductModel.is_active.is_(True),
            ProductModel.show_on_storefront.is_(True),
            ProductModel.id != exclude_product_id,
        ]

        async def _fetch(extra_conditions, order_col, extra_limit: int):
            if extra_limit <= 0:
                return []
            stock_expr = _stock_expr(warehouse_ids) if warehouse_ids else None
            stock_col = (
                func.coalesce(stock_expr, 0) if stock_expr is not None else literal(0)
            ).label("stock")
            stmt = (
                select(ProductModel, TenantModel, CategoryModel, stock_col)
                .join(TenantModel, TenantModel.id == ProductModel.tenant_id)
                .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
                .where(*base_conditions, *extra_conditions)
                .order_by(order_col)
                .limit(extra_limit)
            )
            return (await self._session.execute(stmt)).all()

        # 1. Совпадение по названию категории (как category в GET /marketplace/products)
        rows = []
        seen_ids: set[int] = set()
        if category_name is not None:
            rows = await _fetch(
                [CategoryModel.name == category_name],
                ProductModel.id.desc(),
                limit,
            )
            seen_ids = {product.id for product, _, _, _ in rows}

        # 2. Добор по похожести названия, если совпадений по категории не хватило
        remaining = limit - len(rows)
        if remaining > 0 and name_words:
            exclude_ids = seen_ids | {exclude_product_id}
            extra_conditions = [ProductModel.id.not_in(exclude_ids)] if exclude_ids else []
            if await self._pg_trgm_available():
                query_text = " ".join(name_words)
                similarity_expr = func.similarity(ProductModel.name, query_text)
                more_rows = await _fetch(
                    [*extra_conditions, similarity_expr > 0.1],
                    similarity_expr.desc(),
                    remaining,
                )
            else:
                # ILIKE по каждому значимому слову — совпадение любого из них
                # (обычно 2 слова: имя товара часто отличается брендом/моделью,
                # AND по обоим сильно сузил бы выборку до почти пустой)
                like_conditions = [
                    ProductModel.name.ilike(f"%{word}%") for word in name_words
                ]
                more_rows = await _fetch(
                    [*extra_conditions, or_(*like_conditions)],
                    ProductModel.id.desc(),
                    remaining,
                )
            rows = [*rows, *more_rows]

        if not rows:
            return []

        product_ids = [product.id for product, _, _, _ in rows]
        sold_counts = await self.sold_count_by_products(product_ids)
        ratings = await self.rating_by_products(product_ids)
        _empty_rating = ProductRatingAggregate(average_rating=0.0, reviews_count=0)
        new_cutoff = datetime.now(timezone.utc) - timedelta(days=_NEW_WINDOW_DAYS)

        def _row(product, tenant, category_model, stock) -> MarketplaceProductRow:
            discount_percent = _compute_discount_percent(product.retail_price, product.compare_at_price)
            return MarketplaceProductRow(
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
                shop_logo=tenant.logo,
                shop_is_verified=tenant.is_verified,
                shop_city=tenant.city,
                old_price=product.compare_at_price if discount_percent is not None else None,
                discount_percent=discount_percent,
                is_new=_as_utc(product.created_at) >= new_cutoff,
                is_hit=False,  # список похожих товаров не участвует в подсчёте хитов платформы
            )

        return [_row(*row) for row in rows]


def _compute_discount_percent(retail_price: Decimal, compare_at_price: Decimal | None) -> int | None:
    if compare_at_price is None or compare_at_price <= retail_price:
        return None
    percent = int((compare_at_price - retail_price) / compare_at_price * 100)
    return percent if percent >= 3 else None


def _as_utc(value: datetime) -> datetime:
    """created_at приходит из Postgres как aware datetime (DateTime(timezone=True)),
    но на всякий случай подстрахуемся, если где-то встретится naive (например, в
    тестовых фикстурах, создающих модели напрямую)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
