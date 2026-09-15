from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.marketplace.list_products import (
    ListMarketplaceProductsCommand,
    ListMarketplaceProductsResult,
)
from app.domain.marketplace.repository import MarketplaceProductRow


class MarketplaceCatalogParams(BaseModel):
    query: str = ""
    category: str | None = None
    price_min: Decimal | None = Field(None, ge=0)
    price_max: Decimal | None = Field(None, ge=0)
    in_stock_only: bool = False
    variant_size: str | None = None
    variant_color: str | None = None
    shop_slug: str | None = None
    sort: str = "name"  # name, price_asc, price_desc, created_desc
    limit: int = Field(50, le=50)
    offset: int = Field(0, ge=0)

    model_config = {"extra": "forbid"}

    def to_command(self) -> ListMarketplaceProductsCommand:
        return ListMarketplaceProductsCommand(
            query=self.query,
            category=self.category,
            price_min=self.price_min,
            price_max=self.price_max,
            in_stock_only=self.in_stock_only,
            variant_size=self.variant_size,
            variant_color=self.variant_color,
            shop_slug=self.shop_slug,
            sort=self.sort,
            limit=self.limit,
            offset=self.offset,
        )


class MarketplaceProductResponse(BaseModel):
    id: int
    name: str
    retail_price: Decimal
    photo: str
    category_name: str | None
    in_stock: bool
    min_order_qty: Decimal | None
    order_step_qty: Decimal | None
    shop_slug: str
    shop_name: str

    @classmethod
    def from_row(cls, row: MarketplaceProductRow) -> "MarketplaceProductResponse":
        return cls(
            id=row.product_id,
            name=row.name,
            retail_price=row.retail_price,
            photo=row.photo,
            category_name=row.category_name,
            in_stock=row.in_stock,
            min_order_qty=row.min_order_qty,
            order_step_qty=row.order_step_qty,
            shop_slug=row.shop_slug,
            shop_name=row.shop_name,
        )


class MarketplaceCatalogResponse(BaseModel):
    products: list[MarketplaceProductResponse]
    total: int

    @classmethod
    def from_result(cls, result: ListMarketplaceProductsResult) -> "MarketplaceCatalogResponse":
        return cls(
            products=[MarketplaceProductResponse.from_row(p) for p in result.products],
            total=result.total,
        )
