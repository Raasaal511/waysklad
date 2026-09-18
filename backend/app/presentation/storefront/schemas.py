from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.storefront.accept_request import AcceptStorefrontRequestCommand
from app.application.storefront.create_request import (
    CreateStorefrontRequestCommand,
    StorefrontRequestItemInput,
)
from app.application.storefront.get_catalog import (
    GetStorefrontCatalogCommand,
    StorefrontCatalogResult,
    StorefrontCategoryCount,
)
from app.application.customers.list_my_requests import MyStorefrontRequestItem
from app.application.storefront.get_product import StorefrontProductResult, VariantStock
from app.application.storefront.get_request_status import StorefrontRequestStatusResult
from app.application.storefront.send_message import (
    SendStaffStorefrontMessageCommand,
    SendStorefrontMessageCommand,
)
from app.domain.catalog.entities import Category, Product, ProductVariant
from app.domain.orders.entities import Order
from app.domain.reviews.repository import ProductRatingAggregate
from app.domain.storefront.entities import StorefrontMessage, StorefrontRequest

_EMPTY_RATING = ProductRatingAggregate(average_rating=0.0, reviews_count=0)


class StorefrontCatalogParams(BaseModel):
    query: str = ""
    limit: int = Field(50, le=50)
    offset: int = Field(0, ge=0)
    category_id: int | None = None
    warehouse_id: int | None = None  # витрина одного склада — см. ?warehouse=<id>
    sort: str = "name"  # name, price_asc, price_desc, created_desc, popular, rating, discount
    min_price: Decimal | None = Field(None, ge=0)
    max_price: Decimal | None = Field(None, ge=0)
    in_stock_only: bool = False
    with_discount: bool = False
    variant_size: str | None = None
    variant_color: str | None = None
    min_rating: int | None = Field(None, ge=1, le=5)

    model_config = {"extra": "forbid"}

    def to_command(self, slug: str) -> GetStorefrontCatalogCommand:
        return GetStorefrontCatalogCommand(
            slug=slug,
            query=self.query,
            limit=self.limit,
            offset=self.offset,
            category_id=self.category_id,
            warehouse_id=self.warehouse_id,
            sort=self.sort,
            min_price=self.min_price,
            max_price=self.max_price,
            in_stock_only=self.in_stock_only,
            with_discount=self.with_discount,
            variant_size=self.variant_size,
            variant_color=self.variant_color,
            min_rating=self.min_rating,
        )


class StorefrontCategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None
    product_count: int

    @classmethod
    def from_count(cls, item: StorefrontCategoryCount) -> "StorefrontCategoryResponse":
        return cls(
            id=item.category.id,
            name=item.category.name,
            parent_id=item.category.parent_id,
            product_count=item.product_count,
        )


class StorefrontProductResponse(BaseModel):
    """Урезанный ответ для покупателя — без закупочной цены и точного остатка."""

    id: int
    name: str
    retail_price: Decimal
    old_price: Decimal | None  # None и при отсутствии скидки, и когда retail_price подняли выше compare_at_price
    discount_percent: int | None  # округление вниз, только при >= 3%
    photo: str
    category_id: int | None
    in_stock: bool
    min_order_qty: Decimal | None
    order_step_qty: Decimal | None
    sold_count: Decimal
    average_rating: float
    reviews_count: int

    @classmethod
    def from_entity(
        cls,
        product: Product,
        in_stock: bool,
        sold_count: Decimal = Decimal("0"),
        rating: ProductRatingAggregate = _EMPTY_RATING,
    ) -> "StorefrontProductResponse":
        return cls(
            id=product.id,
            name=product.name,
            retail_price=product.retail_price.amount,
            old_price=product.old_price.amount if product.old_price is not None else None,
            discount_percent=product.discount_percent,
            photo=product.photo,
            category_id=product.category_id,
            in_stock=in_stock,
            min_order_qty=product.storefront_min_qty,
            order_step_qty=product.storefront_step_qty,
            sold_count=sold_count,
            average_rating=rating.average_rating,
            reviews_count=rating.reviews_count,
        )


class StorefrontWarehouseResponse(BaseModel):
    id: int
    name: str
    address: str


class StorefrontCatalogResponse(BaseModel):
    shop_name: str
    products: list[StorefrontProductResponse]
    categories: list[StorefrontCategoryResponse]
    warehouses: list[StorefrontWarehouseResponse]
    available_sizes: list[str]
    available_colors: list[str]
    total: int

    @classmethod
    def from_result(cls, result: StorefrontCatalogResult) -> "StorefrontCatalogResponse":
        return cls(
            shop_name=result.shop_name,
            products=[
                StorefrontProductResponse.from_entity(
                    p,
                    p.id in result.in_stock_product_ids,
                    result.sold_count_by_product_id.get(p.id, Decimal("0")),
                    result.rating_by_product_id.get(p.id, _EMPTY_RATING),
                )
                for p in result.products
            ],
            categories=[StorefrontCategoryResponse.from_count(c) for c in result.categories],
            warehouses=[
                StorefrontWarehouseResponse(id=w.id, name=w.name, address=w.address)
                for w in result.warehouses
            ],
            available_sizes=result.available_sizes,
            available_colors=result.available_colors,
            total=result.total,
        )


def _variant_display_name(variant: ProductVariant, index: int) -> str:
    """name, если задан; иначе «color · size» без пустых частей; иначе
    «Вариант N» (index — 1-based позиция варианта в списке товара)."""
    if variant.name.strip():
        return variant.name.strip()
    parts = [p for p in (variant.color.strip(), variant.size.strip()) if p]
    if parts:
        return " · ".join(parts)
    return f"Вариант {index}"


class StorefrontProductVariantResponse(BaseModel):
    id: int
    size: str
    color: str
    photo: str
    price: Decimal | None
    name: str
    display_name: str
    in_stock: bool
    stock_level: str
    stock_qty: str | None  # заполнен только если у магазина включена настройка витрины

    @classmethod
    def from_entity(
        cls, variant: ProductVariant, index: int, stock: VariantStock | None, show_stock_qty: bool
    ) -> "StorefrontProductVariantResponse":
        resolved_stock = stock or VariantStock(
            variant_id=variant.id or 0, in_stock=False, stock_level="out", quantity=Decimal("0.000")
        )
        return cls(
            id=variant.id,
            size=variant.size,
            color=variant.color,
            photo=variant.photo,
            price=variant.price.amount if variant.price else None,
            name=variant.name,
            display_name=_variant_display_name(variant, index),
            in_stock=resolved_stock.in_stock,
            stock_level=resolved_stock.stock_level,
            stock_qty=str(resolved_stock.quantity) if show_stock_qty else None,
        )


class StorefrontCategoryRefResponse(BaseModel):
    id: int
    name: str


class StorefrontProductCategoryResponse(BaseModel):
    id: int
    name: str
    parent: StorefrontCategoryRefResponse | None

    @classmethod
    def from_entity(cls, category: Category, parent: Category | None) -> "StorefrontProductCategoryResponse":
        return cls(
            id=category.id,
            name=category.name,
            parent=StorefrontCategoryRefResponse(id=parent.id, name=parent.name)
            if parent is not None
            else None,
        )


class StorefrontProductDetailResponse(StorefrontProductResponse):
    """Карточка одного товара — то же самое, что в списке, плюс варианты
    (размер/цвет) для полноты информации на отдельной странице/при шеринге."""

    sku: str
    description: str
    warranty_text: str
    storefront_photos: list[str]
    variants: list[StorefrontProductVariantResponse]
    stock_level: str
    stock_qty: str | None
    category: StorefrontProductCategoryResponse | None
    unit_code: str
    unit_label: str
    views_90d: int

    @classmethod
    def from_entity(
        cls,
        product: Product,
        in_stock: bool,
        sold_count: Decimal = Decimal("0"),
        rating: ProductRatingAggregate = _EMPTY_RATING,
    ) -> "StorefrontProductDetailResponse":
        """Облегчённый конструктор без остатков по видимым складам магазина,
        категории и просмотров — для мест, где их ещё не считают (сейчас:
        GET /api/marketplace/products/{id}, см. MarketplaceProductPageResponse).
        Публичная карточка одной витрины (GetStorefrontProductUseCase) всегда
        идёт через from_result() — с честными stock_level/stock_qty/category."""
        base = StorefrontProductResponse.from_entity(product, in_stock, sold_count, rating)
        fallback_level = "in" if in_stock else "out"
        return cls(
            **base.model_dump(),
            sku=product.sku,
            description=product.description,
            warranty_text=product.warranty_text,
            storefront_photos=list(product.storefront_photos),
            variants=[
                StorefrontProductVariantResponse.from_entity(v, index, None, False)
                for index, v in enumerate(product.variants, start=1)
            ],
            stock_level=fallback_level,
            stock_qty=None,
            category=None,
            unit_code=product.unit.code,
            unit_label=product.unit.name,
            views_90d=0,
        )

    @classmethod
    def from_result(cls, result: StorefrontProductResult) -> "StorefrontProductDetailResponse":
        product = result.product
        base = StorefrontProductResponse.from_entity(
            product, result.in_stock, result.sold_count, result.rating
        )
        return cls(
            **base.model_dump(),
            sku=product.sku,
            description=product.description,
            warranty_text=product.warranty_text,
            storefront_photos=list(product.storefront_photos),
            variants=[
                StorefrontProductVariantResponse.from_entity(
                    v, index, result.variant_stock.get(v.id) if v.id is not None else None,
                    result.show_stock_qty,
                )
                for index, v in enumerate(product.variants, start=1)
            ],
            stock_level=result.stock_level,
            stock_qty=str(result.stock_qty) if result.stock_qty is not None else None,
            category=StorefrontProductCategoryResponse.from_entity(
                result.category.category, result.category.parent
            )
            if result.category is not None
            else None,
            unit_code=product.unit.code,
            unit_label=product.unit.name,
            views_90d=result.views_90d,
        )


class StorefrontProductPageResponse(BaseModel):
    shop_name: str
    product: StorefrontProductDetailResponse

    @classmethod
    def from_result(cls, result: StorefrontProductResult) -> "StorefrontProductPageResponse":
        return cls(
            shop_name=result.shop_name,
            product=StorefrontProductDetailResponse.from_result(result),
        )


class StorefrontRequestItemRequest(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)
    variant_id: int | None = None


class CreateStorefrontRequestRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=200)
    items: list[StorefrontRequestItemRequest] = Field(min_length=1)
    note: str = Field("", max_length=1000)

    model_config = {"extra": "forbid"}

    def to_command(self, slug: str, customer_id: int) -> CreateStorefrontRequestCommand:
        return CreateStorefrontRequestCommand(
            slug=slug,
            customer_id=customer_id,
            customer_name=self.customer_name,
            items=[
                StorefrontRequestItemInput(
                    product_id=i.product_id, quantity=i.quantity, variant_id=i.variant_id
                )
                for i in self.items
            ],
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
    insufficient_stock_at_request: bool

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
            insufficient_stock_at_request=request.insufficient_stock_at_request,
        )


class StorefrontRequestCreatedResponse(StorefrontRequestResponse):
    """Только ответ на создание заявки — единственный момент, когда покупатель
    узнаёт свой access_token (дальше хранит его сам, сервер не показывает повторно)."""

    access_token: str

    @classmethod
    def from_entity(cls, request: StorefrontRequest) -> "StorefrontRequestCreatedResponse":
        base = StorefrontRequestResponse.from_entity(request)
        return cls(**base.model_dump(), access_token=request.access_token)


class MyStorefrontRequestResponse(StorefrontRequestResponse):
    """Для авторизованного покупателя — список его заявок по всем магазинам
    платформы, с названием магазина (владелец видит только свои, ему это
    поле не нужно — см. StorefrontRequestResponse)."""

    shop_name: str

    @classmethod
    def from_item(cls, item: MyStorefrontRequestItem) -> "MyStorefrontRequestResponse":
        base = StorefrontRequestResponse.from_entity(item.request)
        return cls(**base.model_dump(), shop_name=item.shop_name)


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


class StorefrontRequestOrderSummary(BaseModel):
    """Детали заказа, в который превратилась заявка — только после accept."""

    due_date: date
    total: Decimal
    prepayment: Decimal
    to_pay: Decimal
    status: str

    @classmethod
    def from_entity(cls, order: Order) -> "StorefrontRequestOrderSummary":
        return cls(
            due_date=order.due_date,
            total=order.total.amount,
            prepayment=order.prepayment.amount,
            to_pay=order.to_pay.amount,
            status=order.status.value,
        )


class StorefrontRequestStatusResponse(BaseModel):
    status: str
    order: StorefrontRequestOrderSummary | None

    @classmethod
    def from_result(cls, result: StorefrontRequestStatusResult) -> "StorefrontRequestStatusResponse":
        return cls(
            status=result.request.status.value,
            order=StorefrontRequestOrderSummary.from_entity(result.order) if result.order else None,
        )


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
