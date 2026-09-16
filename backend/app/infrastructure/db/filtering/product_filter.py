from sqlalchemy import func, select
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


class ProductFilterFactory(BaseQueryFilterFactory[ProductModel]):
    model = ProductModel
    allowed_order_fields = {"name", "retail_price", "margin", "created_at", "stock"}

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
        }
