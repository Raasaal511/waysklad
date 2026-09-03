from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.storefront.get_catalog import GetStorefrontCatalogCommand, StorefrontCatalogResult
from app.domain.catalog.entities import Category, Product


class StorefrontCatalogParams(BaseModel):
    query: str = ""
    limit: int = Field(50, le=200)
    offset: int = Field(0, ge=0)
    category_id: int | None = None

    model_config = {"extra": "forbid"}

    def to_command(self, slug: str) -> GetStorefrontCatalogCommand:
        return GetStorefrontCatalogCommand(
            slug=slug,
            query=self.query,
            limit=self.limit,
            offset=self.offset,
            category_id=self.category_id,
        )


class StorefrontCategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None

    @classmethod
    def from_entity(cls, category: Category) -> "StorefrontCategoryResponse":
        return cls(id=category.id, name=category.name, parent_id=category.parent_id)


class StorefrontProductResponse(BaseModel):
    """Урезанный ответ для покупателя — без закупочной цены и точного остатка."""

    id: int
    name: str
    retail_price: Decimal
    photo: str
    category_id: int | None
    in_stock: bool

    @classmethod
    def from_entity(cls, product: Product, in_stock: bool) -> "StorefrontProductResponse":
        return cls(
            id=product.id,
            name=product.name,
            retail_price=product.retail_price.amount,
            photo=product.photo,
            category_id=product.category_id,
            in_stock=in_stock,
        )


class StorefrontCatalogResponse(BaseModel):
    shop_name: str
    products: list[StorefrontProductResponse]
    categories: list[StorefrontCategoryResponse]
    total: int

    @classmethod
    def from_result(cls, result: StorefrontCatalogResult) -> "StorefrontCatalogResponse":
        return cls(
            shop_name=result.shop_name,
            products=[
                StorefrontProductResponse.from_entity(p, p.id in result.in_stock_product_ids)
                for p in result.products
            ],
            categories=[StorefrontCategoryResponse.from_entity(c) for c in result.categories],
            total=result.total,
        )
