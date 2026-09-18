"""Админка баннеров платформы (/api/admin/banners) — функции без Actor/Permission,
как и остальной admin-модуль (см. platform_categories.py для того же стиля)."""

from dataclasses import dataclass
from datetime import date

from app.domain.catalog.ports import IFileStorage
from app.domain.common.cache import ICache
from app.domain.common.exceptions import DomainError, NotFoundError
from app.domain.platform.banners import (
    PlatformBanner,
    validate_banner_link,
    validate_placement,
    validate_theme,
)
from app.infrastructure.cache.cache_aside import invalidate_marketplace_cache
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

# баннер — не фотография товара (телефонный оригинал), а уже подготовленная
# промо-картинка на десктоп/мобилку — 3 МБ достаточно с запасом (см. M-B2 п.1)
MAX_BANNER_IMAGE_SIZE = 3 * 1024 * 1024


@dataclass(frozen=True)
class BannerFields:
    placement: str
    title: str
    subtitle: str = ""
    button_text: str = ""
    link: str = ""
    theme: str = "light"
    sort_order: int = 0
    starts_at: date | None = None
    ends_at: date | None = None
    city: str | None = None
    is_active: bool = True


def _validate(fields: BannerFields) -> None:
    if not fields.title.strip():
        raise DomainError("Заголовок баннера не может быть пустым")
    validate_placement(fields.placement)
    validate_theme(fields.theme)
    validate_banner_link(fields.link)
    if fields.starts_at is not None and fields.ends_at is not None and fields.starts_at > fields.ends_at:
        raise DomainError("Дата начала показа баннера не может быть позже даты окончания")


async def list_all_platform_banners(session_factory) -> list[PlatformBanner]:
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        return await uow.platform_banners.list_all()


async def create_platform_banner(
    session_factory, cache: ICache | None, fields: BannerFields
) -> PlatformBanner:
    _validate(fields)
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        banner = PlatformBanner(
            id=None,
            placement=fields.placement,
            title=fields.title.strip(),
            subtitle=fields.subtitle.strip(),
            button_text=fields.button_text.strip(),
            link=fields.link.strip(),
            theme=fields.theme,
            sort_order=fields.sort_order,
            is_active=fields.is_active,
            starts_at=fields.starts_at,
            ends_at=fields.ends_at,
            city=fields.city,
        )
        banner = await uow.platform_banners.add(banner)
        await uow.commit()
    await invalidate_marketplace_cache(cache)
    return banner


async def update_platform_banner(
    session_factory, cache: ICache | None, banner_id: int, fields: BannerFields
) -> PlatformBanner | None:
    _validate(fields)
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        current = await uow.platform_banners.get(banner_id)
        if current is None:
            return None
        banner = PlatformBanner(
            id=banner_id,
            placement=fields.placement,
            title=fields.title.strip(),
            subtitle=fields.subtitle.strip(),
            button_text=fields.button_text.strip(),
            link=fields.link.strip(),
            image=current.image,
            image_mobile=current.image_mobile,
            theme=fields.theme,
            sort_order=fields.sort_order,
            is_active=fields.is_active,
            starts_at=fields.starts_at,
            ends_at=fields.ends_at,
            city=fields.city,
        )
        banner = await uow.platform_banners.save(banner)
        await uow.commit()
    await invalidate_marketplace_cache(cache)
    return banner


async def delete_platform_banner(
    session_factory, cache: ICache | None, storage: IFileStorage, banner_id: int
) -> PlatformBanner | None:
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        banner = await uow.platform_banners.get(banner_id)
        if banner is None:
            return None
        await uow.platform_banners.delete(banner_id)
        await uow.commit()
    for image in (banner.image, banner.image_mobile):
        if image:
            storage.delete(image)
    await invalidate_marketplace_cache(cache)
    return banner


async def set_platform_banner_image(
    session_factory,
    cache: ICache | None,
    storage: IFileStorage,
    banner_id: int,
    filename: str,
    content: bytes,
    *,
    mobile: bool = False,
) -> PlatformBanner:
    if len(content) > MAX_BANNER_IMAGE_SIZE:
        raise DomainError("Картинка баннера слишком большая (максимум 3 МБ)")
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        current = await uow.platform_banners.get(banner_id)
        if current is None:
            raise NotFoundError(f"Баннер {banner_id} не найден")
        old_image = current.image_mobile if mobile else current.image
        image = storage.save(filename, content)
        if mobile:
            banner = await uow.platform_banners.set_image(banner_id, image_mobile=image)
        else:
            banner = await uow.platform_banners.set_image(banner_id, image=image)
        await uow.commit()
    if old_image:
        storage.delete(old_image)
    await invalidate_marketplace_cache(cache)
    return banner
