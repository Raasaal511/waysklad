from dataclasses import dataclass

from sqlalchemy import select

from app.infrastructure.db.models.identity import TenantModel


@dataclass(frozen=True)
class TenantListItem:
    id: int
    name: str
    slug: str | None
    storefront_enabled: bool
    is_suspended: bool
    is_verified: bool
    created_at: str


async def list_tenants(session_factory) -> list[TenantListItem]:
    """Только базовые поля Tenant — без агрегатов (кол-во пользователей/товаров
    и т.п.) на каждую строку списка, это дорого при большом числе магазинов.
    Агрегаты — в карточке одного магазина (get_tenant_detail.py)."""
    async with session_factory() as session:
        models = (
            await session.execute(select(TenantModel).order_by(TenantModel.created_at.desc()))
        ).scalars()
        return [
            TenantListItem(
                id=m.id,
                name=m.name,
                slug=m.slug,
                storefront_enabled=m.storefront_enabled,
                is_suspended=m.is_suspended,
                is_verified=m.is_verified,
                created_at=m.created_at.isoformat(),
            )
            for m in models
        ]
