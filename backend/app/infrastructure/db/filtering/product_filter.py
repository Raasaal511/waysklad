from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.sql.functions import concat

from app.domain.filtering.operators import Operator
from app.infrastructure.db.filtering.field_spec import (
    BOOL_OPS,
    DATE_OPS,
    FieldSpec,
    NUMERIC_OPS,
    TEXT_OPS,
)
from app.infrastructure.db.filtering.filter_factory import BaseQueryFilterFactory
from app.infrastructure.db.models.catalog import ProductModel
from app.infrastructure.db.models.inventory import StockItemModel
from app.infrastructure.db.models.reviews import ReviewModel
from app.infrastructure.db.models.sales import SaleLineModel, SaleModel, SaleReturnLineModel, SaleReturnModel

_POPULAR_WINDOW_DAYS = 30


def _stock_expr(warehouse_id: int | None = None, warehouse_ids: list[int] | None = None):
    """Суммарный остаток товара — по конкретному складу, по списку складов
    (например, только видимые на витрине) либо по всем сразу."""
    conditions = [StockItemModel.product_id == ProductModel.id]
    if warehouse_id is not None:
        conditions.append(StockItemModel.warehouse_id == warehouse_id)
    elif warehouse_ids is not None:
        conditions.append(StockItemModel.warehouse_id.in_(warehouse_ids))
    return (
        select(func.coalesce(func.sum(StockItemModel.quantity), 0))
        .where(*conditions)
        .correlate(ProductModel)
        .scalar_subquery()
    )


def _rating_expr():
    """Средний рейтинг товара по видимым (не скрытым владельцем) отзывам —
    NULL, если отзывов нет (не 0, чтобы GTE-фильтр не путал «нет отзывов» с
    «средняя оценка ноль», которой не может быть — rating всегда 1..5)."""
    return (
        select(func.avg(ReviewModel.rating))
        .where(
            ReviewModel.product_id == ProductModel.id,
            ReviewModel.is_hidden.is_(False),
        )
        .correlate(ProductModel)
        .scalar_subquery()
    )


def _search_text_expr():
    """name/sku/barcode склеены через разделитель — один ilike ловит совпадение в любом из них."""
    return concat(
        ProductModel.name, "\x1f",
        func.coalesce(ProductModel.sku, ""), "\x1f",
        func.coalesce(ProductModel.barcode, ""),
    )


def _discount_percent_expr():
    """int(floor((old-retail)/old*100)), NULL при отсутствии старой цены/скидки
    или когда скидка меньше 3% — та же формула и порог, что Product.discount_percent
    в домене (M-B1 п.4/6), иначе with_discount=true/sort=discount не совпадали бы
    с тем, что реально показывается в ответе."""
    old = ProductModel.compare_at_price
    percent = func.floor((old - ProductModel.retail_price) / old * 100)
    return case(
        (old.is_not(None) & (old > ProductModel.retail_price) & (percent >= 3), percent),
        else_=None,
    )


def _sold_count_30d_expr():
    """Продано (за вычетом возвратов) за последние 30 дней — для sort=popular (M-B1 п.6)."""
    since = datetime.now(timezone.utc) - timedelta(days=_POPULAR_WINDOW_DAYS)
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


class ProductFilterFactory(BaseQueryFilterFactory[ProductModel]):
    model = ProductModel
    allowed_order_fields = {
        "name", "retail_price", "margin", "created_at", "stock",
        "average_rating", "discount_percent", "sold_count_30d",
    }

    @classmethod
    def build_fields(
        cls, warehouse_id: int | None = None, warehouse_ids: list[int] | None = None
    ) -> dict[str, FieldSpec]:
        return {
            "name": FieldSpec(ProductModel.name, TEXT_OPS),
            "sku": FieldSpec(ProductModel.sku, TEXT_OPS),
            "barcode": FieldSpec(ProductModel.barcode, TEXT_OPS),
            "search_text": FieldSpec(_search_text_expr(), frozenset({Operator.ILIKE})),
            "category_id": FieldSpec(ProductModel.category_id, NUMERIC_OPS),
            "retail_price": FieldSpec(ProductModel.retail_price, NUMERIC_OPS),
            "purchase_price": FieldSpec(ProductModel.purchase_price, NUMERIC_OPS),
            "margin": FieldSpec(ProductModel.retail_price - ProductModel.purchase_price, NUMERIC_OPS),
            "created_at": FieldSpec(ProductModel.created_at, DATE_OPS),
            "stock": FieldSpec(_stock_expr(warehouse_id, warehouse_ids), NUMERIC_OPS),
            "show_on_storefront": FieldSpec(ProductModel.show_on_storefront, BOOL_OPS),
            "average_rating": FieldSpec(_rating_expr(), NUMERIC_OPS),
            "discount_percent": FieldSpec(_discount_percent_expr(), NUMERIC_OPS),
            "sold_count_30d": FieldSpec(_sold_count_30d_expr(), NUMERIC_OPS),
        }
