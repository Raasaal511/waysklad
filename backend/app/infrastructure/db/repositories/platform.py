from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.exceptions import NotFoundError
from app.domain.platform.banners import PlatformBanner
from app.domain.platform.entities import PlatformCategory
from app.domain.platform.repository import IPlatformBannerRepository, IPlatformCategoryRepository
from app.infrastructure.db.models.catalog import (
    CategoryModel,
    PlatformBannerModel,
    PlatformCategoryModel,
)


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


def _banner_to_entity(model: PlatformBannerModel) -> PlatformBanner:
    return PlatformBanner(
        id=model.id,
        placement=model.placement,
        title=model.title,
        subtitle=model.subtitle,
        button_text=model.button_text,
        link=model.link,
        image=model.image,
        image_mobile=model.image_mobile,
        theme=model.theme,
        sort_order=model.sort_order,
        is_active=model.is_active,
        starts_at=model.starts_at,
        ends_at=model.ends_at,
        city=model.city,
    )


class SqlAlchemyPlatformBannerRepository(IPlatformBannerRepository):
    """Глобальный справочник баннеров, без tenant_id — тот же принцип, что и
    у SqlAlchemyPlatformCategoryRepository (сессия напрямую)."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, banner: PlatformBanner) -> PlatformBanner:
        model = PlatformBannerModel(
            placement=banner.placement,
            title=banner.title,
            subtitle=banner.subtitle,
            button_text=banner.button_text,
            link=banner.link,
            image=banner.image,
            image_mobile=banner.image_mobile,
            theme=banner.theme,
            sort_order=banner.sort_order,
            is_active=banner.is_active,
            starts_at=banner.starts_at,
            ends_at=banner.ends_at,
            city=banner.city,
        )
        self._session.add(model)
        await self._session.flush()
        banner.id = model.id
        return banner

    async def save(self, banner: PlatformBanner) -> PlatformBanner:
        model = await self._session.get(PlatformBannerModel, banner.id)
        if model is None:
            raise NotFoundError(f"Баннер {banner.id} не найден")
        model.placement = banner.placement
        model.title = banner.title
        model.subtitle = banner.subtitle
        model.button_text = banner.button_text
        model.link = banner.link
        model.theme = banner.theme
        model.sort_order = banner.sort_order
        model.is_active = banner.is_active
        model.starts_at = banner.starts_at
        model.ends_at = banner.ends_at
        model.city = banner.city
        await self._session.flush()
        return _banner_to_entity(model)

    async def get(self, banner_id: int) -> PlatformBanner | None:
        model = await self._session.get(PlatformBannerModel, banner_id)
        return _banner_to_entity(model) if model else None

    async def list_all(self) -> list[PlatformBanner]:
        models = (
            await self._session.execute(
                select(PlatformBannerModel).order_by(
                    PlatformBannerModel.placement, PlatformBannerModel.sort_order
                )
            )
        ).scalars().all()
        return [_banner_to_entity(m) for m in models]

    async def list_live(self, today: date, city: str | None) -> list[PlatformBanner]:
        conditions = [
            PlatformBannerModel.is_active.is_(True),
            or_(
                PlatformBannerModel.starts_at.is_(None), PlatformBannerModel.starts_at <= today
            ),
            or_(PlatformBannerModel.ends_at.is_(None), PlatformBannerModel.ends_at >= today),
        ]
        if city is not None:
            # баннер без city (показывается везде) ИЛИ с этим конкретным городом
            conditions.append(
                or_(PlatformBannerModel.city.is_(None), PlatformBannerModel.city == city)
            )
        models = (
            await self._session.execute(
                select(PlatformBannerModel)
                .where(and_(*conditions))
                .order_by(PlatformBannerModel.sort_order)
            )
        ).scalars().all()
        return [_banner_to_entity(m) for m in models]

    async def set_image(
        self, banner_id: int, image: str | None = None, image_mobile: str | None = None
    ) -> PlatformBanner:
        model = await self._session.get(PlatformBannerModel, banner_id)
        if model is None:
            raise NotFoundError(f"Баннер {banner_id} не найден")
        if image is not None:
            model.image = image
        if image_mobile is not None:
            model.image_mobile = image_mobile
        await self._session.flush()
        return _banner_to_entity(model)

    async def delete(self, banner_id: int) -> None:
        model = await self._session.get(PlatformBannerModel, banner_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
