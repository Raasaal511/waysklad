from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.application.products.apply_import import (
    ApplyImportCommand,
    ApplyImportResult,
    ApplyImportRow,
)
from app.application.products.create_category import CreateCategoryCommand
from app.application.products.create_product import CreateProductCommand, VariantInput
from app.application.products.create_unit import CreateUnitCommand
from app.application.products.import_excel import ImportProductsResult, RowError
from app.application.products.import_preview import PreviewProductsResult, PreviewRow
from app.application.products.update_product import (
    UpdateProductCommand,
    UpdateVariantInput,
)
from app.domain.catalog.entities import Category, Product
from app.domain.common.quantity import Unit

_ORDER_BY_ALIASES = {
    "price_asc": "retail_price",
    "price_desc": "-retail_price",
    "margin_desc": "-margin",
    "created_desc": "-created_at",
    "created_asc": "created_at",
    "stock_desc": "-stock",
}


class ProductsFilterParams(BaseModel):
    """Query-параметры списка товаров — форма запроса; преобразование в raw_params
    для generic filter-системы см. to_raw_params()."""

    query: str = ""
    limit: int = Field(50, le=50)
    offset: int = Field(0, ge=0)
    category_id: int | None = None
    sort: str = "name"
    in_stock_only: bool = False
    warehouse_id: int | None = None

    model_config = {"extra": "forbid"}

    def to_raw_params(self) -> dict:
        raw: dict = {
            "limit": self.limit,
            "offset": self.offset,
            "order_by": _ORDER_BY_ALIASES.get(self.sort, self.sort),
            "category_id": self.category_id,
        }
        if self.query.strip():
            raw["search_text__ilike"] = self.query.strip()
        if self.in_stock_only:
            raw["stock__gt"] = 0
        return raw


class VariantCreateRequest(BaseModel):
    size: str = ""
    color: str = ""
    barcode: str | None = None


class VariantUpdateRequest(BaseModel):
    id: int | None = None  # None — новый вариант; отсутствующие в списке удаляются
    size: str = ""
    color: str = ""
    barcode: str | None = None


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    unit_code: str = "pcs"
    purchase_price: Decimal = Decimal("0")
    retail_price: Decimal = Decimal("0")
    sku: str = ""
    barcode: str | None = None
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    show_on_storefront: bool = False
    variants: list[VariantCreateRequest] = []
    initial_stock_warehouse_id: int | None = None
    initial_stock_quantity: Decimal | None = None

    def to_command(self) -> CreateProductCommand:
        return CreateProductCommand(
            name=self.name,
            unit_code=self.unit_code,
            purchase_price=self.purchase_price,
            retail_price=self.retail_price,
            sku=self.sku,
            barcode=self.barcode,
            category_id=self.category_id,
            min_stock=self.min_stock,
            show_on_storefront=self.show_on_storefront,
            variants=[
                VariantInput(size=v.size, color=v.color, barcode=v.barcode)
                for v in self.variants
            ],
            initial_stock_warehouse_id=self.initial_stock_warehouse_id,
            initial_stock_quantity=self.initial_stock_quantity,
        )


class ProductUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    unit_code: str = "pcs"
    purchase_price: Decimal = Decimal("0")
    retail_price: Decimal = Decimal("0")
    sku: str = ""
    barcode: str | None = None
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    photo: str = ""
    show_on_storefront: bool = False
    variants: list[VariantUpdateRequest] = []

    def to_command(self, product_id: int) -> UpdateProductCommand:
        return UpdateProductCommand(
            product_id=product_id,
            name=self.name,
            unit_code=self.unit_code,
            purchase_price=self.purchase_price,
            retail_price=self.retail_price,
            sku=self.sku,
            barcode=self.barcode,
            category_id=self.category_id,
            min_stock=self.min_stock,
            photo=self.photo,
            show_on_storefront=self.show_on_storefront,
            variants=[
                UpdateVariantInput(id=v.id, size=v.size, color=v.color, barcode=v.barcode)
                for v in self.variants
            ],
        )


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: int | None = None

    def to_command(self) -> CreateCategoryCommand:
        return CreateCategoryCommand(name=self.name, parent_id=self.parent_id)


class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None

    @classmethod
    def from_entity(cls, category: Category) -> "CategoryResponse":
        return cls(id=category.id, name=category.name, parent_id=category.parent_id)


class UnitCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=50)
    fractional: bool = False

    def to_command(self) -> CreateUnitCommand:
        return CreateUnitCommand(code=self.code, name=self.name, fractional=self.fractional)


class UnitResponse(BaseModel):
    code: str
    name: str
    fractional: bool

    @classmethod
    def from_entity(cls, unit: Unit) -> "UnitResponse":
        return cls(code=unit.code, name=unit.name, fractional=unit.fractional)


class RowErrorResponse(BaseModel):
    row: int
    message: str

    @classmethod
    def from_entity(cls, error: RowError) -> "RowErrorResponse":
        return cls(row=error.row, message=error.message)


class ImportProductsResponse(BaseModel):
    created: int
    errors: list[RowErrorResponse]

    @classmethod
    def from_result(cls, result: ImportProductsResult) -> "ImportProductsResponse":
        return cls(
            created=result.created,
            errors=[RowErrorResponse.from_entity(e) for e in result.errors],
        )


class ExistingProductSnapshotResponse(BaseModel):
    id: int
    name: str
    sku: str
    barcode: str | None
    unit_code: str
    purchase_price: Decimal
    retail_price: Decimal
    category_id: int | None
    min_stock: Decimal


class DuplicateCandidateResponse(BaseModel):
    matched_by: Literal["barcode", "sku", "name"]
    product: ExistingProductSnapshotResponse


class PreviewRowResponse(BaseModel):
    row: int
    name: str
    sku: str
    barcode: str | None
    unit_code: str
    category_id: int | None
    purchase_price: Decimal | None
    retail_price: Decimal | None
    min_stock: Decimal
    parse_error: str | None
    status: Literal["no_match", "match", "ambiguous_match"]
    candidates: list[DuplicateCandidateResponse]

    @classmethod
    def from_entity(cls, row: PreviewRow) -> "PreviewRowResponse":
        return cls(
            row=row.row,
            name=row.name,
            sku=row.sku,
            barcode=row.barcode,
            unit_code=row.unit_code,
            category_id=row.category_id,
            purchase_price=row.purchase_price,
            retail_price=row.retail_price,
            min_stock=row.min_stock,
            parse_error=row.parse_error,
            status=row.status,
            candidates=[
                DuplicateCandidateResponse(
                    matched_by=c.matched_by,
                    product=ExistingProductSnapshotResponse(
                        id=c.product.id,
                        name=c.product.name,
                        sku=c.product.sku,
                        barcode=c.product.barcode,
                        unit_code=c.product.unit_code,
                        purchase_price=c.product.purchase_price,
                        retail_price=c.product.retail_price,
                        category_id=c.product.category_id,
                        min_stock=c.product.min_stock,
                    ),
                )
                for c in row.candidates
            ],
        )


class PreviewProductsResponse(BaseModel):
    rows: list[PreviewRowResponse]

    @classmethod
    def from_result(cls, result: PreviewProductsResult) -> "PreviewProductsResponse":
        return cls(rows=[PreviewRowResponse.from_entity(r) for r in result.rows])


class ApplyImportRowRequest(BaseModel):
    client_row_id: str
    action: Literal["create", "update", "skip"]
    name: str = ""
    sku: str = ""
    barcode: str | None = None
    unit_code: str = "pcs"
    purchase_price: Decimal = Decimal("0")
    retail_price: Decimal = Decimal("0")
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    existing_product_id: int | None = None


class ApplyImportRequest(BaseModel):
    rows: list[ApplyImportRowRequest]

    def to_command(self) -> ApplyImportCommand:
        return ApplyImportCommand(
            rows=[
                ApplyImportRow(
                    client_row_id=r.client_row_id,
                    action=r.action,
                    name=r.name,
                    sku=r.sku,
                    barcode=r.barcode,
                    unit_code=r.unit_code,
                    purchase_price=r.purchase_price,
                    retail_price=r.retail_price,
                    category_id=r.category_id,
                    min_stock=r.min_stock,
                    existing_product_id=r.existing_product_id,
                )
                for r in self.rows
            ]
        )


class ApplyImportRowErrorResponse(BaseModel):
    client_row_id: str
    message: str


class ApplyImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[ApplyImportRowErrorResponse]

    @classmethod
    def from_result(cls, result: ApplyImportResult) -> "ApplyImportResponse":
        return cls(
            created=result.created,
            updated=result.updated,
            skipped=result.skipped,
            errors=[
                ApplyImportRowErrorResponse(client_row_id=e.client_row_id, message=e.message)
                for e in result.errors
            ],
        )


class VariantResponse(BaseModel):
    id: int
    size: str
    color: str
    barcode: str | None


class ProductResponse(BaseModel):
    id: int
    name: str
    unit_code: str
    retail_price: Decimal
    purchase_price: Decimal | None  # None — у роли нет права видеть закупочную
    margin: Decimal | None
    sku: str
    barcode: str | None
    category_id: int | None
    min_stock: Decimal
    photo: str
    show_on_storefront: bool
    variants: list[VariantResponse]

    @classmethod
    def from_entity(cls, product: Product, show_purchase: bool) -> "ProductResponse":
        return cls(
            id=product.id,
            name=product.name,
            unit_code=product.unit.code,
            retail_price=product.retail_price.amount,
            purchase_price=product.purchase_price.amount if show_purchase else None,
            margin=product.margin.amount if show_purchase else None,
            sku=product.sku,
            barcode=product.barcode.value if product.barcode else None,
            category_id=product.category_id,
            min_stock=product.min_stock,
            photo=product.photo,
            show_on_storefront=product.show_on_storefront,
            variants=[
                VariantResponse(
                    id=v.id,
                    size=v.size,
                    color=v.color,
                    barcode=v.barcode.value if v.barcode else None,
                )
                for v in product.variants
            ],
        )
