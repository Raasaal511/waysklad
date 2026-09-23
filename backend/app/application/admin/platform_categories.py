"""Админка справочника категорий платформы (/api/admin/platform-categories) —
функции без Actor/Permission, как и остальной admin-модуль: авторизация уже
проверена отдельным admin JWT (require_admin_token), это не tenant-scoped
операция (см. set_tenant_suspended.py для того же стиля)."""

from dataclasses import dataclass

from app.domain.catalog.ports import IFileStorage
from app.domain.common.exceptions import DomainError, NotFoundError
from app.domain.platform.entities import PlatformCategory
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class CreatePlatformCategoryCommand:
    name: str
    slug: str
    sort_order: int = 0
    parent_id: int | None = None


@dataclass(frozen=True)
class UpdatePlatformCategoryCommand:
    category_id: int
    name: str
    slug: str
    sort_order: int = 0
    is_active: bool = True
    parent_id: int | None = None


async def _validate_parent(uow: SqlAlchemyUnitOfWork, parent_id: int | None, own_id: int | None) -> None:
    if parent_id is None:
        return
    if parent_id == own_id:
        raise DomainError("Категория не может быть родителем самой себе")
    parent = await uow.platform_categories.get(parent_id)
    if parent is None:
        raise DomainError("Родительская категория не найдена")
    if parent.parent_id is not None:
        raise DomainError("Допускается только один уровень вложенности категорий")


async def list_all_platform_categories(session_factory) -> list[PlatformCategory]:
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        return await uow.platform_categories.list_all()


async def create_platform_category(
    session_factory, cmd: CreatePlatformCategoryCommand
) -> PlatformCategory:
    if not cmd.name.strip():
        raise DomainError("Название категории не может быть пустым")
    if not cmd.slug.strip():
        raise DomainError("Slug категории не может быть пустым")
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        existing = await uow.platform_categories.get_by_slug(cmd.slug)
        if existing is not None:
            raise DomainError(f"Slug «{cmd.slug}» уже занят")
        await _validate_parent(uow, cmd.parent_id, own_id=None)
        category = PlatformCategory(
            id=None, name=cmd.name.strip(), slug=cmd.slug.strip(),
            sort_order=cmd.sort_order, parent_id=cmd.parent_id,
        )
        category = await uow.platform_categories.add(category)
        await uow.commit()
        return category


async def update_platform_category(
    session_factory, cmd: UpdatePlatformCategoryCommand
) -> PlatformCategory | None:
    if not cmd.name.strip():
        raise DomainError("Название категории не может быть пустым")
    if not cmd.slug.strip():
        raise DomainError("Slug категории не может быть пустым")
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        current = await uow.platform_categories.get(cmd.category_id)
        if current is None:
            return None
        existing = await uow.platform_categories.get_by_slug(cmd.slug)
        if existing is not None and existing.id != cmd.category_id:
            raise DomainError(f"Slug «{cmd.slug}» уже занят")
        await _validate_parent(uow, cmd.parent_id, own_id=cmd.category_id)
        category = PlatformCategory(
            id=cmd.category_id, name=cmd.name.strip(), slug=cmd.slug.strip(),
            image=current.image, sort_order=cmd.sort_order, is_active=cmd.is_active,
            parent_id=cmd.parent_id,
        )
        category = await uow.platform_categories.save(category)
        await uow.commit()
        return category


async def delete_platform_category(session_factory, category_id: int) -> PlatformCategory | None:
    """Мягкое отключение (is_active=false), если есть привязки (товары/дочерние
    категории) — физическое удаление иначе (см. промпт M-B1 п.1)."""
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        category = await uow.platform_categories.get(category_id)
        if category is None:
            return None
        has_bindings = await uow.platform_categories.has_bindings(category_id)
        if has_bindings:
            category.is_active = False
            category = await uow.platform_categories.save(category)
            await uow.commit()
            return category
        await uow.platform_categories.delete(category_id)
        await uow.commit()
        return category


async def set_platform_category_image(
    session_factory, storage: IFileStorage, category_id: int, filename: str, content: bytes
) -> PlatformCategory:
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        current = await uow.platform_categories.get(category_id)
        if current is None:
            raise NotFoundError(f"Категория платформы {category_id} не найдена")
        old_image = current.image
        image = storage.save(filename, content)
        category = await uow.platform_categories.set_image(category_id, image)
        await uow.commit()
        if old_image:
            storage.delete(old_image)
        return category
