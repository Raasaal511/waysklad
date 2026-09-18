from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.marketplace.get_product import MarketplaceProductResult
from app.application.marketplace.list_platform_categories import PlatformCategoryWithCount
from app.application.marketplace.list_products import (
    ListMarketplaceProductsCommand,
    ListMarketplaceProductsResult,
)
from app.domain.marketplace.repository import MarketplaceProductRow
from app.presentation.storefront.schemas import StorefrontProductDetailResponse


class PlatformCategoryPublicResponse(BaseModel):
    id: int
    slug: str
    name: str
    image: str
    parent_id: int | None
    products_count: int

    @classmethod
    def from_item(cls, item: PlatformCategoryWithCount) -> "PlatformCategoryPublicResponse":
        return cls(
            id=item.category.id,
            slug=item.category.slug,
            name=item.category.name,
            image=item.category.image,
            parent_id=item.category.parent_id,
            products_count=item.products_count,
        )


class ListPlatformCategoriesResponse(BaseModel):
    categories: list[PlatformCategoryPublicResponse]


class CityResponse(BaseModel):
    name: str
    shops_count: int


class ListCitiesResponse(BaseModel):
    cities: list[CityResponse]


class MarketplaceCatalogParams(BaseModel):
    query: str = ""
    category: str | None = None  # точное совпадение названия — оставлено для совместимости
    platform_category: str | None = None  # slug общего справочника, включает дочерние категории
    city: str | None = None
    price_min: Decimal | None = Field(None, ge=0)
    price_max: Decimal | None = Field(None, ge=0)
    in_stock_only: bool = False
    with_discount: bool = False
    variant_size: str | None = None
    variant_color: str | None = None
    shop_slug: str | None = None
    sort: str = "name"  # name, price_asc, price_desc, created_desc, popular, rating, discount
    limit: int = Field(50, le=50)
    offset: int = Field(0, ge=0)
    min_rating: int | None = Field(None, ge=1, le=5)

    model_config = {"extra": "forbid"}

    def to_command(self) -> ListMarketplaceProductsCommand:
        return ListMarketplaceProductsCommand(
            query=self.query,
            category=self.category,
            platform_category=self.platform_category,
            city=self.city,
            price_min=self.price_min,
            price_max=self.price_max,
            in_stock_only=self.in_stock_only,
            with_discount=self.with_discount,
            variant_size=self.variant_size,
            variant_color=self.variant_color,
            shop_slug=self.shop_slug,
            sort=self.sort,
            limit=self.limit,
            offset=self.offset,
            min_rating=self.min_rating,
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
    sold_count: Decimal
    average_rating: float
    reviews_count: int
    shop_logo: str
    shop_is_verified: bool
    shop_city: str | None
    old_price: Decimal | None
    discount_percent: int | None
    is_new: bool
    is_hit: bool

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
            sold_count=row.sold_count,
            average_rating=row.rating.average_rating,
            reviews_count=row.rating.reviews_count,
            shop_logo=row.shop_logo,
            shop_is_verified=row.shop_is_verified,
            shop_city=row.shop_city,
            old_price=row.old_price,
            discount_percent=row.discount_percent,
            is_new=row.is_new,
            is_hit=row.is_hit,
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


class MarketplaceProductPageResponse(BaseModel):
    """Карточка одного товара из общего каталога платформы — та же модель
    товара, что у одиночной витрины (StorefrontProductDetailResponse), плюс
    shop_slug/shop_name, т.к. вызывающий не знал tenant заранее (в отличие
    от storefront, где slug уже был в URL)."""

    shop_slug: str
    shop_name: str
    shop_logo: str
    shop_is_verified: bool
    shop_city: str | None
    is_new: bool
    is_hit: bool
    product: StorefrontProductDetailResponse

    @classmethod
    def from_result(cls, result: MarketplaceProductResult) -> "MarketplaceProductPageResponse":
        return cls(
            shop_slug=result.shop_slug,
            shop_name=result.shop_name,
            shop_logo=result.shop_logo,
            shop_is_verified=result.shop_is_verified,
            shop_city=result.shop_city,
            is_new=result.is_new,
            is_hit=result.is_hit,
            product=StorefrontProductDetailResponse.from_entity(
                result.product, result.in_stock, result.sold_count, result.rating
            ),
        )
