from __future__ import annotations

from typing import Protocol

from app.domain.platform.entities import PlatformCategory


class IPlatformCategoryRepository(Protocol):
    """Глобальный справочник (без tenant_id) — не наследует SqlAlchemyRepository,
    тот же принцип, что и у IMarketplaceProductRepository."""

    async def add(self, category: PlatformCategory) -> PlatformCategory: ...
    async def save(self, category: PlatformCategory) -> PlatformCategory: ...
    async def get(self, category_id: int) -> PlatformCategory | None: ...
    async def get_by_slug(self, slug: str) -> PlatformCategory | None: ...
    async def list_all(self) -> list[PlatformCategory]:
        """Все категории, включая неактивные — для админки."""
        ...
    async def list_active(self) -> list[PlatformCategory]:
        """Только is_active=True, для публичного справочника/выпадающего списка владельца."""
        ...
    async def set_image(self, category_id: int, image: str) -> PlatformCategory: ...
    async def has_bindings(self, category_id: int) -> bool:
        """Есть ли хоть одна категория магазина (Category.platform_category_id)
        или дочерняя платформенная категория, ссылающаяся на эту — определяет,
        можно ли удалить категорию физически (DELETE — иначе мягкое отключение)."""
        ...
    async def delete(self, category_id: int) -> None:
        """Физическое удаление — вызывать только когда has_bindings() вернул False."""
        ...
