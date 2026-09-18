from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.domain.common.cache import ICache
from app.domain.identity.entities import Warehouse
from app.domain.reviews.repository import ProductRatingAggregate
from app.infrastructure.cache.cache_aside import cached_use_case
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_CACHE_TTL_SECONDS = 60
_EMPTY_RATING = ProductRatingAggregate(average_rating=0.0, reviews_count=0)
# Ниже этого числа принятых заказов orders_count не показываем (см. п.2 промпта):
# у совсем нового магазина «Заказов: 2» скорее пугает покупателя, чем убеждает —
# порог выбран тем же порядком величины, что «минимум 5 продаж» у бейджа «Хит»
# маркетплейса (compute_hit_product_ids), для единообразия сигналов доверия платформы
_MIN_ORDERS_TO_SHOW = 5


def _orders_count_label(count: int) -> str:
    """Буквальные примеры из промпта B2 п.2 — "2000+", "150+", "12" (без "+") —
    определяют правило однозначно: числа ниже 50 показываются точно (не
    "10+", а "12" — иначе небольшой честный магазин выглядел бы, будто
    что-то скрывает), от 50 и выше — округление вниз с шагом, подобранным по
    порядку величины (10/50/100/500/1000), плюс "+". "150+" при шаге 50
    доказывает, что шаг выбирается по диапазону, а не есть один глобальный
    бакет (единый бакет 100 дал бы неверное "100+")."""
    if count < 50:
        return str(count)
    if count < 100:
        step = 10
    elif count < 500:
        step = 50
    elif count < 1000:
        step = 100
    elif count < 5000:
        step = 500
    else:
        step = 1000
    return f"{(count // step) * step}+"


@dataclass(frozen=True)
class GetStorefrontProfileCommand:
    slug: str


@dataclass(frozen=True)
class ShopAddress:
    name: str
    address: str


@dataclass(frozen=True)
class StorefrontProfileResult:
    name: str
    slug: str
    logo: str
    description: str
    on_platform_since: date
    rating: ProductRatingAggregate
    products_count: int
    orders_count: int | None  # None — скрыт для нового магазина, см. _MIN_ORDERS_TO_SHOW
    min_order_total: Decimal | None
    contact_phone: str
    contact_whatsapp: str
    contact_telegram: str
    addresses: list[ShopAddress]
    policy_refund_money: str
    policy_payment: str
    policy_delivery: str
    policy_returns: str

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "logo": self.logo,
            "description": self.description,
            "on_platform_since": self.on_platform_since.isoformat(),
            "rating": {
                "average_rating": self.rating.average_rating,
                "reviews_count": self.rating.reviews_count,
            },
            "products_count": self.products_count,
            "orders_count": self.orders_count,
            "min_order_total": str(self.min_order_total) if self.min_order_total is not None else None,
            "contact_phone": self.contact_phone,
            "contact_whatsapp": self.contact_whatsapp,
            "contact_telegram": self.contact_telegram,
            "addresses": [{"name": a.name, "address": a.address} for a in self.addresses],
            "policy_refund_money": self.policy_refund_money,
            "policy_payment": self.policy_payment,
            "policy_delivery": self.policy_delivery,
            "policy_returns": self.policy_returns,
        }

    @classmethod
    def from_json(cls, d: dict) -> "StorefrontProfileResult":
        rating_d = d.get("rating")
        return cls(
            name=d["name"],
            slug=d["slug"],
            logo=d["logo"],
            description=d["description"],
            on_platform_since=date.fromisoformat(d["on_platform_since"]),
            rating=ProductRatingAggregate(**rating_d) if rating_d else _EMPTY_RATING,
            products_count=d["products_count"],
            orders_count=d.get("orders_count"),
            min_order_total=Decimal(d["min_order_total"]) if d.get("min_order_total") is not None else None,
            contact_phone=d.get("contact_phone", ""),
            contact_whatsapp=d.get("contact_whatsapp", ""),
            contact_telegram=d.get("contact_telegram", ""),
            addresses=[ShopAddress(name=a["name"], address=a["address"]) for a in d.get("addresses", [])],
            policy_refund_money=d.get("policy_refund_money", ""),
            policy_payment=d.get("policy_payment", ""),
            policy_delivery=d.get("policy_delivery", ""),
            policy_returns=d.get("policy_returns", ""),
        )


class GetStorefrontProfileUseCase:
    """Публичный профиль магазина — карточка продавца, FAQ, контакты, адреса
    (промпт B2 п.2). Тот же паттерн, что GetStorefrontCatalogUseCase/
    GetStorefrontProductUseCase: свой UoW на резолвленный tenant_id, cache-aside
    с коротким TTL вместо точной инвалидации (invalidate_shop_cache уже
    вызывается всеми мутациями Tenant/Warehouse/Review, которые сюда попадают)."""

    def __init__(self, session_factory, cache: ICache | None = None):
        self._session_factory = session_factory
        self._cache = cache

    async def _execute_uncached(
        self, cmd: GetStorefrontProfileCommand
    ) -> StorefrontProfileResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
            return None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            counts_by_category = await uow.products.count_storefront_by_category()
            products_count = sum(counts_by_category.values())
            rating = await uow.reviews.rating_for_shop()
            accepted_requests = await uow.storefront_requests.count_accepted()
            sales = await uow.sales.count_all()
            all_warehouses = await uow.warehouses.list()

        orders_count_raw = accepted_requests + sales
        orders_count = orders_count_raw if orders_count_raw >= _MIN_ORDERS_TO_SHOW else None
        visible_warehouses: list[Warehouse] = [w for w in all_warehouses if w.show_on_storefront]

        return StorefrontProfileResult(
            name=tenant.name,
            slug=cmd.slug,
            logo=tenant.logo,
            description=tenant.storefront_description,
            on_platform_since=(tenant.created_at or datetime.now()).date(),
            rating=rating,
            products_count=products_count,
            orders_count=orders_count,
            min_order_total=tenant.storefront_min_order_total,
            contact_phone=tenant.contact_phone,
            contact_whatsapp=tenant.contact_whatsapp,
            contact_telegram=tenant.contact_telegram,
            addresses=[ShopAddress(name=w.name, address=w.address) for w in visible_warehouses],
            policy_refund_money=tenant.policy_refund_money,
            policy_payment=tenant.policy_payment,
            policy_delivery=tenant.policy_delivery,
            policy_returns=tenant.policy_returns,
        )

    execute = cached_use_case(
        "storefront_profile",
        _CACHE_TTL_SECONDS,
        to_json=lambda r: r.to_json(),
        from_json=StorefrontProfileResult.from_json,
        shop_slug=lambda cmd: cmd.slug,
    )(_execute_uncached)


def orders_count_label(count: int) -> str:
    """Публичная обёртка над _orders_count_label — используется presentation-слоем
    (StorefrontProfileResponse), сам расчёт держим в application, не в схеме ответа."""
    return _orders_count_label(count)
