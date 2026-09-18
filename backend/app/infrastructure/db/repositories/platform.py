from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.exceptions import NotFoundError
from app.domain.platform.entities import PlatformCategory
from app.domain.platform.repository import IPlatformCategoryRepository
from app.infrastructure.db.models.catalog import CategoryModel, PlatformCategoryModel


def _to_entity(model: PlatformCategoryModel) -> PlatformCategory:
    return PlatformCategory(
        id=model.id,
        name=model.name,
        slug=model.slug,
        image=model.image,
        sort_order=model.sort_order,
        is_active=model.is_active,
        parent_id=model.parent_id,
    )


class SqlAlchemyPlatformCategoryRepository(IPlatformCategoryRepository):
    """Глобальный справочник, без tenant_id — тот же принцип, что и у
    SqlAlchemyMarketplaceProductRepository (сессия напрямую, не через
    SqlAlchemyRepository._tenant)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, category: PlatformCategory) -> PlatformCategory:
        model = PlatformCategoryModel(
            name=category.name,
            slug=category.slug,
            image=category.image,
            sort_order=category.sort_order,
            is_active=category.is_active,
            parent_id=category.parent_id,
        )
        self._session.add(model)
        await self._session.flush()
        category.id = model.id
        return category

    async def save(self, category: PlatformCategory) -> PlatformCategory:
        model = await self._session.get(PlatformCategoryModel, category.id)
        if model is None:
            raise NotFoundError(f"Категория платформы {category.id} не найдена")
        model.name = category.name
        model.slug = category.slug
        model.image = category.image
        model.sort_order = category.sort_order
        model.is_active = category.is_active
        model.parent_id = category.parent_id
        await self._session.flush()
        return category

    async def get(self, category_id: int) -> PlatformCategory | None:
        model = await self._session.get(PlatformCategoryModel, category_id)
        return _to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> PlatformCategory | None:
        model = (
            await self._session.execute(
                select(PlatformCategoryModel).where(PlatformCategoryModel.slug == slug)
            )
        ).scalar_one_or_none()
        return _to_entity(model) if model else None

    async def list_all(self) -> list[PlatformCategory]:
        models = (
            await self._session.execute(
                select(PlatformCategoryModel).order_by(PlatformCategoryModel.sort_order)
            )
        ).scalars().all()
        return [_to_entity(m) for m in models]

    async def list_active(self) -> list[PlatformCategory]:
        models = (
            await self._session.execute(
                select(PlatformCategoryModel)
                .where(PlatformCategoryModel.is_active.is_(True))
                .order_by(PlatformCategoryModel.sort_order)
            )
        ).scalars().all()
        return [_to_entity(m) for m in models]

    async def set_image(self, category_id: int, image: str) -> PlatformCategory:
        model = await self._session.get(PlatformCategoryModel, category_id)
        if model is None:
            raise NotFoundError(f"Категория платформы {category_id} не найдена")
        model.image = image
        await self._session.flush()
        return _to_entity(model)

    async def has_bindings(self, category_id: int) -> bool:
        shop_ref = (
            await self._session.execute(
                select(CategoryModel.id)
                .where(CategoryModel.platform_category_id == category_id)
                .limit(1)
            )
        ).first()
        if shop_ref is not None:
            return True
        child_ref = (
            await self._session.execute(
                select(PlatformCategoryModel.id)
                .where(PlatformCategoryModel.parent_id == category_id)
                .limit(1)
            )
        ).first()
        return child_ref is not None

    async def delete(self, category_id: int) -> None:
        model = await self._session.get(PlatformCategoryModel, category_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
