from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.storefront.accept_request import AcceptStorefrontRequestCommand
from app.application.storefront.create_request import (
    CreateStorefrontRequestCommand,
    StorefrontRequestItemInput,
)
from app.application.storefront.get_catalog import GetStorefrontCatalogCommand, StorefrontCatalogResult
from app.application.storefront.send_message import (
    SendStaffStorefrontMessageCommand,
    SendStorefrontMessageCommand,
)
from app.domain.catalog.entities import Category, Product
from app.domain.storefront.entities import StorefrontMessage, StorefrontRequest


class StorefrontCatalogParams(BaseModel):
    query: str = ""
    limit: int = Field(50, le=200)
    offset: int = Field(0, ge=0)
    category_id: int | None = None
    warehouse_id: int | None = None  # витрина одного склада — см. ?warehouse=<id>

    model_config = {"extra": "forbid"}

    def to_command(self, slug: str) -> GetStorefrontCatalogCommand:
        return GetStorefrontCatalogCommand(
            slug=slug,
            query=self.query,
            limit=self.limit,
            offset=self.offset,
            category_id=self.category_id,
            warehouse_id=self.warehouse_id,
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


class StorefrontRequestItemRequest(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    variant_id: int | None = None


class CreateStorefrontRequestRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    items: list[StorefrontRequestItemRequest] = Field(min_length=1)
    customer_phone: str = ""
    note: str = Field("", max_length=1000)

    model_config = {"extra": "forbid"}

    def to_command(self, slug: str) -> CreateStorefrontRequestCommand:
        return CreateStorefrontRequestCommand(
            slug=slug,
            customer_name=self.customer_name,
            items=[
                StorefrontRequestItemInput(
                    product_id=i.product_id, quantity=i.quantity, variant_id=i.variant_id
                )
                for i in self.items
            ],
            customer_phone=self.customer_phone,
            note=self.note,
        )


class StorefrontRequestLineResponse(BaseModel):
    product_id: int
    quantity: Decimal
    variant_id: int | None


class StorefrontRequestResponse(BaseModel):
    """Owner-side — без access_token, сотрудник не должен видеть токен покупателя."""

    id: int
    customer_name: str
    customer_phone: str
    note: str
    status: str
    lines: list[StorefrontRequestLineResponse]

    @classmethod
    def from_entity(cls, request: StorefrontRequest) -> "StorefrontRequestResponse":
        return cls(
            id=request.id,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            note=request.note,
            status=request.status.value,
            lines=[
                StorefrontRequestLineResponse(
                    product_id=line.product_id, quantity=line.quantity, variant_id=line.variant_id
                )
                for line in request.lines
            ],
        )


class StorefrontRequestCreatedResponse(StorefrontRequestResponse):
    """Только ответ на создание заявки — единственный момент, когда покупатель
    узнаёт свой access_token (дальше хранит его сам, сервер не показывает повторно)."""

    access_token: str

    @classmethod
    def from_entity(cls, request: StorefrontRequest) -> "StorefrontRequestCreatedResponse":
        base = StorefrontRequestResponse.from_entity(request)
        return cls(**base.model_dump(), access_token=request.access_token)


class AcceptStorefrontRequestRequest(BaseModel):
    warehouse_id: int
    due_date: date
    prepayment: Decimal = Decimal("0")

    def to_command(self, request_id: int) -> AcceptStorefrontRequestCommand:
        return AcceptStorefrontRequestCommand(
            request_id=request_id,
            warehouse_id=self.warehouse_id,
            due_date=self.due_date,
            prepayment=self.prepayment,
        )


class SendStorefrontMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    def to_command(self, access_token: str) -> SendStorefrontMessageCommand:
        return SendStorefrontMessageCommand(access_token=access_token, text=self.text)

    def to_staff_command(self, request_id: int) -> SendStaffStorefrontMessageCommand:
        return SendStaffStorefrontMessageCommand(request_id=request_id, text=self.text)


class StorefrontMessageResponse(BaseModel):
    id: int
    request_id: int
    author: str
    text: str
    created_at: str | None

    @classmethod
    def from_entity(cls, message: StorefrontMessage) -> "StorefrontMessageResponse":
        return cls(
            id=message.id,
            request_id=message.request_id,
            author=message.author.value,
            text=message.text,
            created_at=message.created_at.isoformat() if message.created_at else None,
        )
