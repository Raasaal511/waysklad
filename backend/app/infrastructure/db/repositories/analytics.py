from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.sql.selectable import Subquery

from app.domain.analytics.repository import (
    CategoryProfit,
    DeadStockItem,
    IAnalyticsRepository,
    MissedSaleItem,
    PeriodTotals,
    ProductSales,
    RestockRecommendation,
    StockValueItem,
    TimelineBucket,
    TimelinePoint,
)
from app.infrastructure.db.models.catalog import CategoryModel, ProductModel
from app.infrastructure.db.models.debts import DebtModel
from app.infrastructure.db.models.inventory import StockItemModel
from app.infrastructure.db.models.sales import (
    SaleLineModel,
    SaleModel,
    SaleReturnLineModel,
    SaleReturnModel,
)
from app.infrastructure.db.models.storefront import (
    StorefrontRequestLineModel,
    StorefrontRequestModel,
)
from app.infrastructure.db.repositories.base import SqlAlchemyRepository

_LINE_TOTAL = SaleLineModel.price * SaleLineModel.quantity


def _returned_qty_subquery(tenant_id: int) -> Subquery:
    """Возвращённое количество по каждой строке продажи (частичные возвраты
    суммируются). Строк без единого возврата здесь нет — join с ней всегда
    LEFT, недостающее trактуется как 0."""
    return (
        select(
            SaleReturnLineModel.sale_line_id.label("sale_line_id"),
            func.sum(SaleReturnLineModel.quantity).label("returned_qty"),
        )
        .join(SaleReturnModel, SaleReturnModel.id == SaleReturnLineModel.return_id)
        .where(SaleReturnModel.tenant_id == tenant_id)
        .group_by(SaleReturnLineModel.sale_line_id)
        .subquery()
    )


def _sale_subtotal_subquery(tenant_id: int) -> Subquery:
    """Сумма чека ДО скидки (Sale.subtotal) — нужна, чтобы распределить
    Sale.discount (единая сумма на чек) по строкам пропорционально их доле."""
    return (
        select(
            SaleLineModel.sale_id.label("sale_id"),
            func.sum(_LINE_TOTAL).label("subtotal"),
        )
        .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
        .where(SaleModel.tenant_id == tenant_id)
        .group_by(SaleLineModel.sale_id)
        .subquery()
    )


def _effective_qty(returned: Subquery):
    """Проданное количество за вычетом возвращённого по этой строке."""
    return SaleLineModel.quantity - func.coalesce(returned.c.returned_qty, 0)


def _effective_unit_price(subtotals: Subquery):
    """Цена строки за вычетом доли скидки чека, пропорциональной вкладу
    строки в сумму чека до скидки. subtotal чека без строк с price=0 не может
    быть 0, если у чека есть скидка (Sale.validate: discount <= subtotal) —
    NULLIF на случай вырожденного 0/0 (чек целиком по нулевой цене)."""
    discount_share = SaleModel.discount * SaleLineModel.price / func.nullif(subtotals.c.subtotal, 0)
    return SaleLineModel.price - func.coalesce(discount_share, 0)


def _line_revenue(subtotals: Subquery, returned: Subquery):
    return _effective_unit_price(subtotals) * _effective_qty(returned)


def _line_profit(subtotals: Subquery, returned: Subquery):
    return (_effective_unit_price(subtotals) - SaleLineModel.purchase_price) * _effective_qty(returned)


class SqlAlchemyAnalyticsRepository(SqlAlchemyRepository, IAnalyticsRepository):
    async def totals_for_period(
        self, date_from: datetime, date_to: datetime, warehouse_ids: list[int] | None = None
    ) -> PeriodTotals:
        sale_filter = [
            SaleModel.tenant_id == self._tenant,
            SaleModel.deleted_at.is_(None),
            SaleModel.created_at >= date_from,
            SaleModel.created_at < date_to,
        ]
        if warehouse_ids is not None:
            sale_filter.append(SaleModel.warehouse_id.in_(warehouse_ids))

        sales_count, change_kept = (
            await self._session.execute(
                select(
                    func.count(SaleModel.id),
                    func.coalesce(func.sum(SaleModel.change_kept), 0),
                ).where(*sale_filter)
            )
        ).one()

        subtotals = _sale_subtotal_subquery(self._tenant)
        returned = _returned_qty_subquery(self._tenant)
        revenue, profit = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(_line_revenue(subtotals, returned)), 0),
                    func.coalesce(func.sum(_line_profit(subtotals, returned)), 0),
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(subtotals, subtotals.c.sale_id == SaleModel.id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(*sale_filter)
            )
        ).one()

        return PeriodTotals(
            sales_count=sales_count, revenue=revenue, profit=profit, change_kept=change_kept
        )

    async def revenue_timeline(
        self,
        date_from: datetime,
        date_to: datetime,
        bucket: TimelineBucket,
        warehouse_ids: list[int] | None = None,
    ) -> list[TimelinePoint]:
        sale_filter = [
            SaleModel.tenant_id == self._tenant,
            SaleModel.deleted_at.is_(None),
            SaleModel.created_at >= date_from,
            SaleModel.created_at < date_to,
        ]
        if warehouse_ids is not None:
            sale_filter.append(SaleModel.warehouse_id.in_(warehouse_ids))

        subtotals = _sale_subtotal_subquery(self._tenant)
        returned = _returned_qty_subquery(self._tenant)
        bucket_expr = func.date_trunc(bucket, SaleModel.created_at)
        rows = (
            await self._session.execute(
                select(
                    bucket_expr,
                    func.count(func.distinct(SaleModel.id)),
                    func.coalesce(func.sum(_line_revenue(subtotals, returned)), 0),
                    func.coalesce(func.sum(_line_profit(subtotals, returned)), 0),
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(subtotals, subtotals.c.sale_id == SaleModel.id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(*sale_filter)
                .group_by(bucket_expr)
                .order_by(bucket_expr)
            )
        ).all()
        return [
            TimelinePoint(
                bucket_start=bucket_start.date(), sales_count=count, revenue=revenue, profit=profit,
            )
            for bucket_start, count, revenue, profit in rows
        ]

    async def top_products(
        self,
        date_from: datetime,
        date_to: datetime,
        limit: int = 10,
        warehouse_ids: list[int] | None = None,
    ) -> list[ProductSales]:
        sale_filter = [
            SaleModel.tenant_id == self._tenant,
            SaleModel.deleted_at.is_(None),
            SaleModel.created_at >= date_from,
            SaleModel.created_at < date_to,
        ]
        if warehouse_ids is not None:
            sale_filter.append(SaleModel.warehouse_id.in_(warehouse_ids))

        subtotals = _sale_subtotal_subquery(self._tenant)
        returned = _returned_qty_subquery(self._tenant)
        qty_expr = func.sum(_effective_qty(returned))
        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    qty_expr,
                    func.sum(_line_revenue(subtotals, returned)),
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(ProductModel, ProductModel.id == SaleLineModel.product_id)
                .join(subtotals, subtotals.c.sale_id == SaleModel.id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(*sale_filter)
                .group_by(ProductModel.id, ProductModel.name)
                .order_by(qty_expr.desc())
                .limit(limit)
            )
        ).all()
        return [
            ProductSales(product_id=pid, product_name=name, quantity_sold=qty, revenue=revenue)
            for pid, name, qty, revenue in rows
        ]

    async def profit_by_category(
        self, date_from: datetime, date_to: datetime, warehouse_ids: list[int] | None = None
    ) -> list[CategoryProfit]:
        sale_filter = [
            SaleModel.tenant_id == self._tenant,
            SaleModel.deleted_at.is_(None),
            SaleModel.created_at >= date_from,
            SaleModel.created_at < date_to,
        ]
        if warehouse_ids is not None:
            sale_filter.append(SaleModel.warehouse_id.in_(warehouse_ids))

        subtotals = _sale_subtotal_subquery(self._tenant)
        returned = _returned_qty_subquery(self._tenant)
        profit_expr = func.sum(_line_profit(subtotals, returned))
        rows = (
            await self._session.execute(
                select(
                    CategoryModel.id,
                    func.coalesce(CategoryModel.name, "Без категории"),
                    func.sum(_line_revenue(subtotals, returned)),
                    profit_expr,
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(ProductModel, ProductModel.id == SaleLineModel.product_id)
                .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
                .join(subtotals, subtotals.c.sale_id == SaleModel.id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(*sale_filter)
                .group_by(CategoryModel.id, CategoryModel.name)
                .order_by(profit_expr.desc())
            )
        ).all()
        return [
            CategoryProfit(category_id=cid, category_name=name, revenue=revenue, profit=profit)
            for cid, name, revenue, profit in rows
        ]

    async def dead_stock(
        self, stale_after: date, warehouse_ids: list[int] | None = None
    ) -> list[DeadStockItem]:
        stale_before = datetime.combine(stale_after, datetime.min.time())
        last_sale = (
            select(
                SaleLineModel.product_id.label("product_id"),
                func.max(SaleModel.created_at).label("last_sale_at"),
            )
            .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
            .where(SaleModel.tenant_id == self._tenant, SaleModel.deleted_at.is_(None))
            .group_by(SaleLineModel.product_id)
            .subquery()
        )

        stock_filter = [StockItemModel.tenant_id == self._tenant]
        if warehouse_ids is not None:
            stock_filter.append(StockItemModel.warehouse_id.in_(warehouse_ids))
        stock_qty = (
            select(
                StockItemModel.product_id.label("product_id"),
                func.sum(StockItemModel.quantity).label("quantity"),
            )
            .where(*stock_filter)
            .group_by(StockItemModel.product_id)
            .subquery()
        )

        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    stock_qty.c.quantity,
                    ProductModel.purchase_price,
                    last_sale.c.last_sale_at,
                )
                .join(stock_qty, stock_qty.c.product_id == ProductModel.id)
                .outerjoin(last_sale, last_sale.c.product_id == ProductModel.id)
                .where(
                    ProductModel.tenant_id == self._tenant,
                    ProductModel.is_active.is_(True),
                    stock_qty.c.quantity > 0,
                    func.coalesce(last_sale.c.last_sale_at, datetime.min) < stale_before,
                )
                .order_by(last_sale.c.last_sale_at.asc().nulls_first())
            )
        ).all()
        return [
            DeadStockItem(
                product_id=pid, product_name=name, quantity=qty,
                purchase_price=purchase_price, last_sale_at=last_sale_at,
            )
            for pid, name, qty, purchase_price, last_sale_at in rows
        ]

    async def stock_value(self, warehouse_ids: list[int] | None = None) -> list[StockValueItem]:
        stock_filter = [
            ProductModel.tenant_id == self._tenant,
            StockItemModel.tenant_id == self._tenant,
        ]
        if warehouse_ids is not None:
            stock_filter.append(StockItemModel.warehouse_id.in_(warehouse_ids))

        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    func.sum(StockItemModel.quantity),
                    ProductModel.purchase_price,
                )
                .join(StockItemModel, StockItemModel.product_id == ProductModel.id)
                .where(*stock_filter)
                .group_by(ProductModel.id, ProductModel.name, ProductModel.purchase_price)
                .having(func.sum(StockItemModel.quantity) > 0)
            )
        ).all()
        return [
            StockValueItem(product_id=pid, product_name=name, quantity=qty, purchase_price=price)
            for pid, name, qty, price in rows
        ]

    async def restock_recommendations(
        self, sale_period_from: datetime, warehouse_ids: list[int] | None = None
    ) -> list[RestockRecommendation]:
        stock_filter = [StockItemModel.tenant_id == self._tenant]
        if warehouse_ids is not None:
            stock_filter.append(StockItemModel.warehouse_id.in_(warehouse_ids))
        stock_qty = (
            select(
                StockItemModel.product_id.label("product_id"),
                func.sum(StockItemModel.quantity).label("quantity"),
            )
            .where(*stock_filter)
            .group_by(StockItemModel.product_id)
            .subquery()
        )

        sale_filter = [
            SaleModel.tenant_id == self._tenant,
            SaleModel.deleted_at.is_(None),
            SaleModel.created_at >= sale_period_from,
        ]
        if warehouse_ids is not None:
            sale_filter.append(SaleModel.warehouse_id.in_(warehouse_ids))
        returned = _returned_qty_subquery(self._tenant)
        sold_qty = (
            select(
                SaleLineModel.product_id.label("product_id"),
                func.sum(_effective_qty(returned)).label("quantity_sold"),
            )
            .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
            .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
            .where(*sale_filter)
            .group_by(SaleLineModel.product_id)
            .subquery()
        )

        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    stock_qty.c.quantity,
                    ProductModel.min_stock,
                    sold_qty.c.quantity_sold,
                )
                .join(stock_qty, stock_qty.c.product_id == ProductModel.id)
                .join(sold_qty, sold_qty.c.product_id == ProductModel.id)
                .where(
                    ProductModel.tenant_id == self._tenant,
                    stock_qty.c.quantity <= ProductModel.min_stock,
                )
                .order_by(sold_qty.c.quantity_sold.desc())
            )
        ).all()
        return [
            RestockRecommendation(
                product_id=pid, product_name=name, quantity=qty,
                min_stock=min_stock, quantity_sold=sold,
            )
            for pid, name, qty, min_stock, sold in rows
        ]

    async def debts_issued_total(self, date_from: datetime, date_to: datetime) -> Decimal:
        total = (
            await self._session.execute(
                select(func.coalesce(func.sum(DebtModel.amount), 0)).where(
                    DebtModel.tenant_id == self._tenant,
                    DebtModel.client_id.is_not(None),
                    DebtModel.issued_at >= date_from.date(),
                    DebtModel.issued_at < date_to.date(),
                )
            )
        ).scalar_one()
        return total

    async def missed_sales(
        self, date_from: datetime, date_to: datetime
    ) -> list[MissedSaleItem]:
        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    func.count(func.distinct(StorefrontRequestModel.id)),
                    func.sum(StorefrontRequestLineModel.quantity),
                )
                .select_from(StorefrontRequestLineModel)
                .join(
                    StorefrontRequestModel,
                    StorefrontRequestModel.id == StorefrontRequestLineModel.request_id,
                )
                .join(ProductModel, ProductModel.id == StorefrontRequestLineModel.product_id)
                .where(
                    StorefrontRequestModel.tenant_id == self._tenant,
                    StorefrontRequestModel.insufficient_stock_at_request.is_(True),
                    StorefrontRequestModel.created_at >= date_from,
                    StorefrontRequestModel.created_at < date_to,
                )
                .group_by(ProductModel.id, ProductModel.name)
                .order_by(func.count(func.distinct(StorefrontRequestModel.id)).desc())
            )
        ).all()
        return [
            MissedSaleItem(
                product_id=pid,
                product_name=name,
                requests_count=requests_count,
                quantity_requested=quantity,
            )
            for pid, name, requests_count, quantity in rows
        ]

    async def sold_count_by_products(self, product_ids: list[int]) -> dict[int, Decimal]:
        if not product_ids:
            return {}
        returned = _returned_qty_subquery(self._tenant)
        rows = (
            await self._session.execute(
                select(SaleLineModel.product_id, func.sum(_effective_qty(returned)))
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .outerjoin(returned, returned.c.sale_line_id == SaleLineModel.id)
                .where(
                    SaleModel.tenant_id == self._tenant,
                    SaleModel.deleted_at.is_(None),
                    SaleLineModel.product_id.in_(product_ids),
                )
                .group_by(SaleLineModel.product_id)
            )
        ).all()
        return {pid: quantity for pid, quantity in rows}
