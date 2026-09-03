from dataclasses import dataclass
from typing import Literal, Protocol

from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Category, Product
from app.domain.common.quantity import Unit


@dataclass(frozen=True)
class DuplicateLookupKey:
    """Ключи одной строки импорта для поиска дублей."""

    row_index: int  # индекс строки в исходном файле (для сборки ответа)
    name: str
    sku: str = ""
    barcode: str | None = None


@dataclass(frozen=True)
class DuplicateMatch:
    row_index: int
    product: Product
    matched_by: Literal["barcode", "sku", "name"]


class IProductRepository(Protocol):
    async def add(self, product: Product) -> Product: ...
    async def save(self, product: Product) -> Product: ...
    async def get(self, product_id: int) -> Product: ...
    async def search_all(self, query: str = "") -> list[Product]: ...
    async def list_filtered(self, raw_params: dict, warehouse_id: int | None = None) -> tuple[list[Product], int]: ...
    async def get_by_barcode(self, barcode: Barcode) -> Product | None: ...
    async def find_duplicates(self, keys: list[DuplicateLookupKey]) -> list[DuplicateMatch]: ...
    async def count_storefront_by_category(self) -> dict[int | None, int]:
        """Сколько товаров с show_on_storefront=True в каждой категории —
        для навигации на публичной витрине («Одежда (12)»). Ключ None — товары
        без категории."""
        ...


class IUnitRepository(Protocol):
    async def add(self, unit: Unit) -> Unit: ...
    async def get(self, code: str) -> Unit | None: ...
    async def list(self) -> list[Unit]: ...


class ICategoryRepository(Protocol):
    async def add(self, category: Category) -> Category: ...
    async def get(self, category_id: int) -> Category: ...
    async def list(self) -> list[Category]: ...

