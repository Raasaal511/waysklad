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
    async def deactivate(self, product_id: int) -> None: ...
    async def delete(self, product_id: int) -> None:
        """Физическое удаление. Вызывающий должен убедиться, что товар нигде
        не фигурирует (has_activity вернул False) — сам метод это не проверяет."""
        ...
    async def has_activity(self, product_id: int) -> bool:
        """Есть ли у товара хоть одно упоминание за пределами каталога: продажи,
        заказы, заявки с витрины, складские документы (приёмка/списание/
        перемещение), задачи. Определяет, можно ли удалить товар физически."""
        ...
    async def search_all(self, query: str = "") -> list[Product]: ...
    async def list_filtered(
        self,
        raw_params: dict,
        warehouse_id: int | None = None,
        warehouse_ids: list[int] | None = None,
        variant_size: str | None = None,
        variant_color: str | None = None,
    ) -> tuple[list[Product], int]: ...
    async def get_by_barcode(self, barcode: Barcode) -> Product | None: ...
    async def find_duplicates(self, keys: list[DuplicateLookupKey]) -> list[DuplicateMatch]: ...
    async def count_storefront_by_category(self) -> dict[int | None, int]:
        """Сколько товаров с show_on_storefront=True в каждой категории —
        для навигации на публичной витрине («Одежда (12)»). Ключ None — товары
        без категории."""
        ...
    async def list_storefront_variant_options(self) -> tuple[list[str], list[str]]:
        """Уникальные непустые size/color среди вариантов товаров, видимых на
        витрине (show_on_storefront=True) — для построения фильтра «Размер»/
        «Цвет» на публичной странице. Возвращает (sizes, colors)."""
        ...


class IUnitRepository(Protocol):
    async def add(self, unit: Unit) -> Unit: ...
    async def get(self, code: str) -> Unit | None: ...
    async def list(self) -> list[Unit]: ...


class ICategoryRepository(Protocol):
    async def add(self, category: Category) -> Category: ...
    async def get(self, category_id: int) -> Category: ...
    async def list(self) -> list[Category]: ...

