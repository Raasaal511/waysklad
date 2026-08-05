from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.domain.analytics.repository import (
    CategoryProfit,
    DeadStockItem,
    IAnalyticsRepository,
    PeriodTotals,
    ProductSales,
    StockValueItem,
)
from app.infrastructure.db.models.catalog import CategoryModel, ProductModel
from app.infrastructure.db.models.debts import DebtModel
from app.infrastructure.db.models.inventory import StockItemModel
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel
from app.infrastructure.db.repositories.base import SqlAlchemyRepository

_LINE_PROFIT = (SaleLineModel.price - SaleLineModel.purchase_price) * SaleLineModel.quantity
_LINE_REVENUE = SaleLineModel.price * SaleLineModel.quantity


class SqlAlchemyAnalyticsRepository(SqlAlchemyRepository, IAnalyticsRepository):
    async def totals_for_period(self, date_from: datetime, date_to: datetime) -> PeriodTotals:
        sales_count = (
            await self._session.execute(
                select(func.count(SaleModel.id)).where(
                    SaleModel.tenant_id == self._tenant,
                    SaleModel.created_at >= date_from,
                    SaleModel.created_at < date_to,
                )
            )
        ).scalar_one()

        revenue, profit = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(_LINE_REVENUE), 0),
                    func.coalesce(func.sum(_LINE_PROFIT), 0),
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .where(
                    SaleModel.tenant_id == self._tenant,
                    SaleModel.created_at >= date_from,
                    SaleModel.created_at < date_to,
                )
            )
        ).one()

        return PeriodTotals(sales_count=sales_count, revenue=revenue, profit=profit)

    async def top_products(
        self, date_from: datetime, date_to: datetime, limit: int = 10
    ) -> list[ProductSales]:
        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    func.sum(SaleLineModel.quantity),
                    func.sum(_LINE_REVENUE),
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(ProductModel, ProductModel.id == SaleLineModel.product_id)
                .where(
                    SaleModel.tenant_id == self._tenant,
                    SaleModel.created_at >= date_from,
                    SaleModel.created_at < date_to,
                )
                .group_by(ProductModel.id, ProductModel.name)
                .order_by(func.sum(SaleLineModel.quantity).desc())
                .limit(limit)
            )
        ).all()
        return [
            ProductSales(product_id=pid, product_name=name, quantity_sold=qty, revenue=revenue)
            for pid, name, qty, revenue in rows
        ]

    async def profit_by_category(
        self, date_from: datetime, date_to: datetime
    ) -> list[CategoryProfit]:
        rows = (
            await self._session.execute(
                select(
                    CategoryModel.id,
                    func.coalesce(CategoryModel.name, "Без категории"),
                    func.sum(_LINE_REVENUE),
                    func.sum(_LINE_PROFIT),
                )
                .select_from(SaleLineModel)
                .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
                .join(ProductModel, ProductModel.id == SaleLineModel.product_id)
                .outerjoin(CategoryModel, CategoryModel.id == ProductModel.category_id)
                .where(
                    SaleModel.tenant_id == self._tenant,
                    SaleModel.created_at >= date_from,
                    SaleModel.created_at < date_to,
                )
                .group_by(CategoryModel.id, CategoryModel.name)
                .order_by(func.sum(_LINE_PROFIT).desc())
            )
        ).all()
        return [
            CategoryProfit(category_id=cid, category_name=name, revenue=revenue, profit=profit)
            for cid, name, revenue, profit in rows
        ]

    async def dead_stock(self, stale_after: date) -> list[DeadStockItem]:
        stale_before = datetime.combine(stale_after, datetime.min.time())
        last_sale = (
            select(
                SaleLineModel.product_id.label("product_id"),
                func.max(SaleModel.created_at).label("last_sale_at"),
            )
            .join(SaleModel, SaleModel.id == SaleLineModel.sale_id)
            .where(SaleModel.tenant_id == self._tenant)
            .group_by(SaleLineModel.product_id)
            .subquery()
        )

        stock_qty = (
            select(
                StockItemModel.product_id.label("product_id"),
                func.sum(StockItemModel.quantity).label("quantity"),
            )
            .where(StockItemModel.tenant_id == self._tenant)
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

    async def stock_value(self) -> list[StockValueItem]:
        rows = (
            await self._session.execute(
                select(
                    ProductModel.id,
                    ProductModel.name,
                    func.sum(StockItemModel.quantity),
                    ProductModel.purchase_price,
                )
                .join(StockItemModel, StockItemModel.product_id == ProductModel.id)
                .where(
                    ProductModel.tenant_id == self._tenant,
                    StockItemModel.tenant_id == self._tenant,
                )
                .group_by(ProductModel.id, ProductModel.name, ProductModel.purchase_price)
                .having(func.sum(StockItemModel.quantity) > 0)
            )
        ).all()
        return [
            StockValueItem(product_id=pid, product_name=name, quantity=qty, purchase_price=price)
            for pid, name, qty, price in rows
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
