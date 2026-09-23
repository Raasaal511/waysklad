"""Демо-данные публичных страниц (маркетплейс, витрина) для дизайн-работы
над карточкой товара/каталогом (см. `docs/PRODUCT_PAGE_PROMPTS.md`, шаг P0).

ТОЛЬКО ДЛЯ DEV/STAGING. Ни при каких обстоятельствах не запускать в проде —
скрипт создаёт настоящие магазины, товары, отзывы и продажи прямым обходом
части бизнес-правил (например, отзывы и заявки создаются напрямую через
репозитории, а не через полный JWT-флоу покупателя) ради скорости и
идемпотентности. Требует явного флага --yes, иначе завершится без изменений.

Создаёт:
    - 2 магазина: «Демо-маркет» (demo-market, Грозный, проверенный, с лого,
      мин. заказ 1000 ₽) и «Второй магазин» (demo-second, Гудермес);
    - у каждого — склад с show_on_storefront, описание, контакты, политики;
    - 24 товара в первом магазине, 10 во втором, по 4-6 категориям;
    - остатки: часть «нет в наличии», часть «мало», часть с запасом;
    - продажи с разным количеством — чтобы были «хиты» (sold_count);
    - отзывы у трёх товаров (5-20 шт, с тегами/фото/голосами), у одного —
      ровно один отзыв, у остальных — ноль;
    - 2 hero + 2 promo баннера платформы.

Идемпотентен: повторный запуск находит уже созданные магазины/товары по
slug/sku и не плодит дубли (см. _get_or_create_tenant, _get_or_create_product).

Запуск (в docker, чтобы видеть ту же БД, что и приложение на localhost:5173):
    docker compose exec backend python backend/scripts/seed_public_demo.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import random
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import update as sa_update

from app.application.admin.platform_banners import (
    BannerFields,
    create_platform_banner,
    set_platform_banner_image,
)
from app.application.admin.set_tenant_verified import set_tenant_verified
from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.application.auth.update_shop import UpdateShopCommand, UpdateShopUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.create_warehouse import CreateWarehouseCommand, CreateWarehouseUseCase
from app.application.products.create_category import CreateCategoryCommand, CreateCategoryUseCase
from app.application.products.create_product import (
    CreateProductCommand,
    CreateProductUseCase,
    VariantInput,
)
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.sales.create_sale import CreateSaleCommand, CreateSaleUseCase, SaleItemInput
from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer
from app.domain.identity.permissions import Actor
from app.domain.reviews.entities import Review
from app.domain.reviews.tags import REVIEW_TAGS
from app.domain.sales.payment import PaymentMethod
from app.domain.storefront.entities import (
    StorefrontRequest,
    StorefrontRequestLine,
    StorefrontRequestStatus,
)
from app.infrastructure.db.models.identity import TenantModel
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.files import LocalFileStorage
from app.infrastructure.security import BcryptPasswordHasher

RNG = random.Random(20260919)  # фиксированный seed — воспроизводимые данные между запусками

# Копии картинок из frontend/public/ — скопированы один раз в backend/scripts/demo_assets/,
# чтобы скрипт работал внутри backend-контейнера, где смонтирован только ./backend
# (docker-compose не пробрасывает ./frontend в backend-сервис). Источник — те же
# файлы, что в frontend/public/{hero-banner,onbarding,logo,logo-mark,logo-mark-dark}.png,
# внешние картинки не скачиваются.
DEMO_ASSETS = Path(__file__).resolve().parent / "demo_assets"
SOURCE_IMAGES = [
    DEMO_ASSETS / "hero-banner.png",
    DEMO_ASSETS / "onbarding.png",
    DEMO_ASSETS / "logo.png",
    DEMO_ASSETS / "logo-mark.png",
    DEMO_ASSETS / "logo-mark-dark.png",
]

storage = LocalFileStorage()
_uploaded_cache: dict[str, str] = {}


def _upload(source: Path, tag: str) -> str:
    """Загружает локальный PNG через LocalFileStorage (та же обработка/webp,
    что у реальной загрузки) под новым сгенерированным именем. tag — только
    для дифференциации кэша (одна и та же картинка может переиспользоваться
    под разными тегами, чтобы не плодить одинаковые файлы на каждый вызов)."""
    key = f"{source}:{tag}"
    if key in _uploaded_cache:
        return _uploaded_cache[key]
    content = source.read_bytes()
    url = storage.save(source.name, content)
    _uploaded_cache[key] = url
    return url


def _random_photo(tag: str) -> str:
    source = RNG.choice(SOURCE_IMAGES)
    return _upload(source, tag)


@dataclass(frozen=True)
class ShopSpec:
    shop_name: str
    slug: str
    owner_name: str
    phone: str
    city: str
    verified: bool
    logo_source: Path
    min_order_total: Decimal | None
    warehouse_name: str
    warehouse_address: str
    description: str
    contact_phone: str
    contact_whatsapp: str
    contact_telegram: str
    policy_refund_money: str
    policy_payment: str
    policy_delivery: str
    policy_returns: str
    product_count: int


SHOPS = [
    ShopSpec(
        shop_name="Демо-маркет",
        slug="demo-market",
        owner_name="Ахмед Демидов",
        phone="+79280005001",
        city="Грозный",
        verified=True,
        logo_source=DEMO_ASSETS / "logo.png",
        min_order_total=Decimal("1000"),
        warehouse_name="Склад на Триумфальной",
        warehouse_address="г. Грозный, пр-т Путина, 5",
        description=(
            "Крупный магазин электроники, одежды и товаров для дома. Работаем "
            "с 2019 года, доставляем по всей Чечне."
        ),
        contact_phone="+79280005001",
        contact_whatsapp="+79280005001",
        contact_telegram="demo_market_shop",
        policy_refund_money=(
            "Деньги возвращаются на карту в течение 3 рабочих дней после "
            "возврата товара на склад. При оплате наличными — возврат в кассе "
            "магазина."
        ),
        policy_payment=(
            "Принимаем оплату картой при получении, переводом на карту и "
            "наличными курьеру. Предоплата не требуется для заказов до 20000 ₽."
        ),
        policy_delivery=(
            "Доставка по Грозному — 1-2 дня, по республике — 2-4 дня. "
            "Стоимость доставки уточняйте у менеджера при оформлении заказа."
        ),
        policy_returns=(
            "Возврат товара надлежащего качества — в течение 14 дней, если "
            "сохранены товарный вид и упаковка. Брак меняем в течение 30 дней."
        ),
        product_count=24,
    ),
    ShopSpec(
        shop_name="Второй магазин",
        slug="demo-second",
        owner_name="Хава Байсарова",
        phone="+79280005002",
        city="Гудермес",
        verified=False,
        logo_source=DEMO_ASSETS / "logo-mark.png",
        min_order_total=None,
        warehouse_name="Склад в центре",
        warehouse_address="г. Гудермес, ул. Ленина, 12",
        description="Небольшой магазин одежды и аксессуаров ручной работы.",
        contact_phone="+79280005002",
        contact_whatsapp="",
        contact_telegram="",
        policy_refund_money="Возврат денег — переводом в течение 5 дней.",
        policy_payment="",
        policy_delivery="Доставка только по Гудермесу, курьером.",
        policy_returns="",
        product_count=10,
    ),
]

CATEGORY_SETS = {
    "demo-market": [
        ("Электроника", None),
        ("Одежда", None),
        ("Обувь", None),
        ("Для дома", None),
        ("Аксессуары", None),
        ("Красота", None),
    ],
    "demo-second": [
        ("Одежда", None),
        ("Аксессуары", None),
        ("Обувь", None),
        ("Красота", None),
    ],
}

# platform_category slug на каждую категорию магазина, для сопоставления
PLATFORM_SLUG_BY_NAME = {
    "Электроника": "electronics",
    "Одежда": "clothing",
    "Обувь": "shoes",
    "Для дома": "home",
    "Аксессуары": "accessories",
    "Красота": "beauty",
}

PRODUCT_NAME_POOL = {
    "Электроника": [
        "Наушники беспроводные Sonic",
        "Powerbank 20000 мАч",
        "Смарт-часы Pulse",
        "Колонка портативная Wave",
        "Кабель USB-C 2м",
        "Зарядное устройство 65W",
    ],
    "Одежда": [
        "Футболка базовая",
        "Худи оверсайз",
        "Платье летнее",
        "Джинсы классик",
        "Куртка ветровка",
        "Свитер вязаный",
    ],
    "Обувь": [
        "Кроссовки спортивные",
        "Ботинки зимние",
        "Туфли классические",
        "Сандалии летние",
    ],
    "Для дома": [
        "Набор посуды 12 предметов",
        "Плед флисовый",
        "Светильник настольный",
        "Органайзер для хранения",
    ],
    "Аксессуары": [
        "Рюкзак городской",
        "Ремень кожаный",
        "Кошелёк мужской",
        "Сумка через плечо",
    ],
    "Красота": [
        "Набор для ухода за кожей",
        "Фен профессиональный",
        "Парфюм унисекс",
        "Косметичка дорожная",
    ],
}

REVIEW_TEXTS_POSITIVE = [
    "Отличный товар, всё пришло вовремя, качество на высоте!",
    "Пользуюсь уже месяц — полностью доволен покупкой.",
    "Заказывал не в первый раз, всегда всё хорошо упаковано.",
    "Соответствует описанию, цвет как на фото.",
    "Отличное качество за свою цену, рекомендую!",
    "Быстрая доставка, продавец на связи, товар супер.",
    "То что нужно, купил в подарок — понравилось.",
    "Хорошая вещь, буду заказывать ещё.",
]
REVIEW_TEXTS_MIXED = [
    "В целом неплохо, но упаковка была немного помята.",
    "Товар хороший, но доставка задержалась на пару дней.",
    "Качество среднее, ожидал большего за эти деньги.",
    "Нормально, но размер немного не подошёл — пришлось подгонять.",
]
REVIEW_AUTHOR_NAMES = [
    "Ахмед", "Хава", "Ислам", "Айна", "Магомед", "Зарема", "Рустам", "Полла",
    "Тимур", "Дана", "Ваха", "Малика", "Иса", "Асет", "Бекхан", "Луиза",
    "Адам", "Сацита", "Хусейн", "Кока",
]


async def _get_or_create_tenant(spec: ShopSpec) -> tuple[int, Actor]:
    hasher = BcryptPasswordHasher()
    async with SqlAlchemyUnitOfWork(None) as uow:
        existing_user = await uow.users.get_by_phone(spec.phone)
    if existing_user is not None:
        return existing_user.tenant_id, Actor(id=existing_user.id, role=existing_user.role)

    result = await RegisterShopUseCase(SqlAlchemyUnitOfWork(None), hasher).execute(
        RegisterShopCommand(
            shop_name=spec.shop_name,
            owner_name=spec.owner_name,
            phone=spec.phone,
            password="demo12345",
        )
    )
    owner = result.owner
    return owner.tenant_id, Actor(id=owner.id, role=owner.role)


async def _configure_shop(tenant_id: int, actor: Actor, spec: ShopSpec) -> None:
    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id)

    logo_url = _upload(spec.logo_source, f"logo:{spec.slug}")
    async with uow() as u:
        tenant = await u.tenants.get(tenant_id)
        tenant.logo = logo_url
        await u.tenants.save(tenant)
        # slug желаемый (demo-market/demo-second) — RegisterShopUseCase сам
        # генерирует slug транслитерацией названия магазина и не принимает
        # свой; для стабильного публичного URL демо-магазина переписываем
        # его напрямую (TenantRepository.save() поле slug не трогает).
        existing_with_slug = await u.tenants.get_by_slug(spec.slug)
        if existing_with_slug is None or existing_with_slug.id == tenant_id:
            await u.session.execute(
                sa_update(TenantModel).where(TenantModel.id == tenant_id).values(slug=spec.slug)
            )
        await u.commit()

    await UpdateShopUseCase(uow()).execute(
        actor,
        UpdateShopCommand(
            name=spec.shop_name,
            storefront_enabled=True,
            city=spec.city,
            storefront_description=spec.description,
            contact_phone=spec.contact_phone,
            contact_whatsapp=spec.contact_whatsapp,
            contact_telegram=spec.contact_telegram,
            storefront_min_order_total=spec.min_order_total,
            policy_refund_money=spec.policy_refund_money,
            policy_payment=spec.policy_payment,
            policy_delivery=spec.policy_delivery,
            policy_returns=spec.policy_returns,
            storefront_show_stock_qty=True,
        ),
    )

    await set_tenant_verified(SessionLocal, None, tenant_id, spec.verified)

    async with uow() as u:
        warehouses = await u.warehouses.list()
    existing_wh = next((w for w in warehouses if w.name == spec.warehouse_name), None)
    if existing_wh is None:
        warehouse = await CreateWarehouseUseCase(uow()).execute(
            actor, CreateWarehouseCommand(name=spec.warehouse_name, address=spec.warehouse_address)
        )
        async with uow() as u:
            await u.warehouses.update_details(
                warehouse.id, warehouse.name, warehouse.address, show_on_storefront=True
            )
            await u.commit()
        warehouse_id = warehouse.id
    else:
        if not existing_wh.show_on_storefront:
            async with uow() as u:
                await u.warehouses.update_details(
                    existing_wh.id, existing_wh.name, existing_wh.address, show_on_storefront=True
                )
                await u.commit()
        warehouse_id = existing_wh.id

    print(f"  Магазин «{spec.shop_name}» (tenant_id={tenant_id}, slug={spec.slug}): настроен, склад id={warehouse_id}")


async def _get_or_create_categories(
    tenant_id: int, actor: Actor, slug: str
) -> dict[str, int]:
    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id)

    async with uow() as u:
        existing = {c.name: c.id for c in await u.categories.list()}
        platform_by_slug = {c.slug: c.id for c in await u.platform_categories.list_all()}

    result: dict[str, int] = {}
    for name, _ in CATEGORY_SETS[slug]:
        if name in existing:
            result[name] = existing[name]
            continue
        platform_category_id = platform_by_slug.get(PLATFORM_SLUG_BY_NAME.get(name, ""))
        category = await CreateCategoryUseCase(uow()).execute(
            actor,
            CreateCategoryCommand(name=name, platform_category_id=platform_category_id),
        )
        result[name] = category.id
    return result


@dataclass
class ProductPlan:
    name: str
    category_name: str
    retail_price: Decimal
    purchase_price: Decimal
    compare_at_price: Decimal | None
    stock_state: str  # "out" | "low" | "in"
    has_description: bool
    has_warranty: bool
    has_min_step: bool
    variant_count: int
    sold_count: int


def _build_product_plans(spec: ShopSpec) -> list[ProductPlan]:
    categories = [name for name, _ in CATEGORY_SETS[spec.slug]]
    plans: list[ProductPlan] = []
    stock_cycle = ["in", "in", "low", "out"]  # 50% in, 25% low, 25% out
    for i in range(spec.product_count):
        category_name = categories[i % len(categories)]
        pool = PRODUCT_NAME_POOL[category_name]
        base_name = pool[i % len(pool)]
        suffix = "" if i < len(pool) else f" {i // len(pool) + 1}"
        name = f"{base_name}{suffix}"

        base_price = Decimal(RNG.randrange(500, 15000, 100))
        purchase_price = (base_price * Decimal("0.6")).quantize(Decimal("1"))

        has_discount = i % 3 == 0
        discount_pct = Decimal(RNG.choice([15, 20, 25, 30, 40, 50]))
        compare_at_price = (
            (base_price / (Decimal("100") - discount_pct) * Decimal("100")).quantize(Decimal("1"))
            if has_discount
            else None
        )

        stock_state = stock_cycle[i % len(stock_cycle)]
        has_description = i % 2 == 0
        has_warranty = i % 4 == 0
        has_min_step = i % 5 == 0
        variant_count = 0 if i % 3 != 0 else RNG.randint(2, 8)
        sold_count = [0, 0, 2, 5, 8, 15, 22, 40][i % 8]

        plans.append(
            ProductPlan(
                name=name,
                category_name=category_name,
                retail_price=base_price,
                purchase_price=purchase_price,
                compare_at_price=compare_at_price,
                stock_state=stock_state,
                has_description=has_description,
                has_warranty=has_warranty,
                has_min_step=has_min_step,
                variant_count=variant_count,
                sold_count=sold_count,
            )
        )
    return plans


LOREM_PARAGRAPHS = [
    "Этот товар отлично подойдёт для повседневного использования. Мы тщательно "
    "отбираем поставщиков, чтобы гарантировать стабильное качество каждой партии.",
    "Материалы, из которых изготовлен товар, проверены на соответствие стандартам "
    "качества. Перед отправкой каждая единица проходит визуальный контроль.",
    "Упаковка защищает товар от повреждений при транспортировке. Если у вас "
    "остались вопросы — напишите нам в чат заявки, ответим в течение дня.",
]


async def _seed_products(
    tenant_id: int,
    actor: Actor,
    spec: ShopSpec,
    category_ids: dict[str, int],
    warehouse_id: int,
) -> list[int]:
    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id)

    async with uow() as u:
        existing_by_sku = {p.sku: p for p in await u.products.search_all()}

    plans = _build_product_plans(spec)
    product_ids: list[int] = []

    for idx, plan in enumerate(plans):
        sku = f"{spec.slug.upper()}-{idx + 1:03d}"
        existing = existing_by_sku.get(sku)
        if existing is not None:
            product_ids.append(existing.id)
            continue

        variants = []
        if plan.variant_count:
            for v in range(plan.variant_count):
                color = RNG.choice(["Чёрный", "Белый", "Красный", "Синий", "Серый", "Бежевый"])
                size = RNG.choice(["S", "M", "L", "XL", ""]) if plan.category_name in ("Одежда", "Обувь") else ""
                variant_price = plan.retail_price + Decimal(RNG.choice([0, 0, 100, 200, -100]))
                variants.append(
                    VariantInput(
                        size=size,
                        color=color,
                        price=variant_price if variant_price > 0 else plan.retail_price,
                        name="" if RNG.random() > 0.3 else f"{plan.name.split()[0]} {chr(65 + v)}",
                    )
                )

        description = "\n\n".join(RNG.sample(LOREM_PARAGRAPHS, k=RNG.randint(1, 3))) if plan.has_description else ""
        warranty_text = "Гарантия производителя — 12 месяцев со дня покупки." if plan.has_warranty else ""

        product = await CreateProductUseCase(uow()).execute(
            actor,
            CreateProductCommand(
                name=plan.name,
                unit_code="pcs",
                sku=sku,
                purchase_price=plan.purchase_price,
                retail_price=plan.retail_price,
                compare_at_price=plan.compare_at_price,
                category_id=category_ids[plan.category_name],
                description=description,
                warranty_text=warranty_text,
                show_on_storefront=True,
                storefront_min_qty=Decimal("2") if plan.has_min_step else None,
                storefront_step_qty=Decimal("2") if plan.has_min_step else None,
                variants=variants,
                min_stock=Decimal("3"),
            ),
        )
        product_ids.append(product.id)

        # остатки — если у товара есть варианты, приходуем на КАЖДЫЙ вариант
        # отдельной строкой (иначе остаток был бы только у товара целиком, а
        # все варианты honestly показывали бы "нет в наличии" — см. B1 п.2:
        # variants[].in_stock считается по остатку именно этого варианта)
        if plan.stock_state != "out":
            qty = Decimal("2") if plan.stock_state == "low" else Decimal(RNG.randint(15, 80))
            if product.variants:
                lines = [
                    LineInput(
                        product_id=product.id,
                        variant_id=variant.id,
                        quantity=qty,
                        cost=plan.purchase_price,
                    )
                    for variant in product.variants
                ]
            else:
                lines = [LineInput(product_id=product.id, quantity=qty, cost=plan.purchase_price)]
            await ReceiveGoodsUseCase(uow()).execute(
                actor,
                ReceiveGoodsCommand(warehouse_id=warehouse_id, lines=lines),
            )

        # Реальных товарных фото у нас нет — единственный источник картинок в
        # demo-данных это брендовые иллюстрации платформы (hero-banner, onbarding,
        # логотипы), и подставлять их как "фото шампуня"/"фото кроссовок" даёт
        # тот самый эффект "одна и та же картинка везде не в тему". Честнее
        # оставить товар без фото — витрина корректно показывает плейсхолдер
        # (см. ProductCard/ProductGallery), это ближе к реальному новому магазину,
        # чем нерелевантная картинка. Фото остаются только там, где по смыслу
        # это именно фото "от покупателя" — см. отзывы, _random_photo ниже.

        print(f"    [{sku}] {plan.name} — цена {plan.retail_price}₽, остаток «{plan.stock_state}», "
              f"вариантов {plan.variant_count}")

    return product_ids


async def _generate_sales(
    tenant_id: int, actor: Actor, spec: ShopSpec, warehouse_id: int, product_ids: list[int]
) -> None:
    """Продажи с разным количеством — источник sold_count (считается динамически
    по Sale, не хранимое поле). Продаём только товары «в наличии» (иначе продажа
    уйдёт в минус остатка)."""

    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id)

    plans = _build_product_plans(spec)
    for product_id, plan in zip(product_ids, plans, strict=True):
        if plan.stock_state == "out" or plan.sold_count <= 0:
            continue
        # продаём меньше, чем на складе (qty приёмки >= 15 для "in"), чтобы
        # не увести остаток в минус — но не больше исходного остатка
        max_sellable = 10 if plan.stock_state == "in" else 1
        qty_to_sell = min(plan.sold_count, max_sellable)
        if qty_to_sell <= 0:
            continue
        try:
            await CreateSaleUseCase(uow()).execute(
                actor,
                CreateSaleCommand(
                    warehouse_id=warehouse_id,
                    payment_method=PaymentMethod.CASH,
                    items=[
                        SaleItemInput(
                            product_id=product_id, quantity=Decimal(qty_to_sell), price=plan.retail_price
                        )
                    ],
                ),
            )
        except DomainError:
            continue  # недостаточно остатка — пропускаем, не критично для демо


async def _get_or_create_customer(phone: str, name: str) -> int:
    async with SqlAlchemyUnitOfWork(None) as uow:
        existing = await uow.customers.get_by_phone(phone)
        if existing is not None:
            return existing.id
        customer = await uow.customers.add(Customer(id=None, phone=Phone(phone), name=name))
        await uow.commit()
        return customer.id


async def _seed_reviews_for_product(tenant_id: int, product_id: int, count: int) -> None:
    """Создаёт count отзывов напрямую через репозитории — обходит JWT-флоу
    покупателя (нет реальных access-токенов в seed-скрипте), но создаёт
    полноценные Customer/StorefrontRequest/Review записи с корректными
    внешними ключами, так же как это сделал бы настоящий покупатель после
    покупки. Голоса (likes/dislikes) расставляются через review_votes напрямую."""
    for i in range(count):
        phone = f"+7928{9000000 + tenant_id * 1000 + product_id * 100 + i:07d}"[:12]
        author_name = REVIEW_AUTHOR_NAMES[(product_id + i) % len(REVIEW_AUTHOR_NAMES)]
        customer_id = await _get_or_create_customer(phone, author_name)

        async with SqlAlchemyUnitOfWork(tenant_id) as uow:
            existing_requests = await uow.storefront_requests.list_by_customer(customer_id)
            request = next(
                (r for r in existing_requests if any(l.product_id == product_id for l in r.lines)),
                None,
            )
            if request is None:
                request = StorefrontRequest(
                    id=None,
                    customer_name=author_name,
                    customer_id=customer_id,
                    customer_phone=phone,
                    lines=[StorefrontRequestLine(product_id=product_id, quantity=Decimal("1"))],
                    status=StorefrontRequestStatus.ACCEPTED,
                    reservation_released=True,
                    access_token=secrets.token_urlsafe(32),
                )
                await uow.storefront_requests.add(request)
                await uow.commit()

            if await uow.reviews.exists_for_request(request.id, product_id):
                continue

            rating = RNG.choices([5, 4, 3, 2, 1], weights=[45, 30, 12, 8, 5])[0]
            text = RNG.choice(REVIEW_TEXTS_POSITIVE if rating >= 4 else REVIEW_TEXTS_MIXED)
            tags = RNG.sample([t.code for t in REVIEW_TAGS], k=RNG.randint(0, 4))
            photos = [_random_photo(f"review-{product_id}-{i}-{n}") for n in range(RNG.randint(0, 2))] \
                if rating >= 4 and RNG.random() < 0.4 else []

            review = Review(
                id=None,
                tenant_id=tenant_id,
                product_id=product_id,
                storefront_request_id=request.id,
                customer_id=customer_id,
                rating=rating,
                text=text,
                author_name=author_name,
                photos=photos,
                tags=tags,
                created_at=datetime.now(timezone.utc) - timedelta(days=RNG.randint(0, 180)),
            )
            review.normalize_photos()
            review.validate()
            await uow.reviews.add(review)
            await uow.commit()

            likes = RNG.randint(0, 20)
            dislikes = RNG.randint(0, 3)
            if likes or dislikes:
                # проставляем голоса от отдельных фейковых покупателей —
                # используем review_votes напрямую по нескольким synthetic customer_id
                for v in range(likes):
                    voter_phone = f"+7928{8000000 + product_id * 100 + i * 10 + v:07d}"[:12]
                    voter_id = await _get_or_create_customer(voter_phone, "Покупатель")
                    if voter_id == customer_id:
                        continue
                    await uow.review_votes.set_vote(tenant_id, review.id, voter_id, 1)
                for v in range(dislikes):
                    voter_phone = f"+7928{7000000 + product_id * 100 + i * 10 + v:07d}"[:12]
                    voter_id = await _get_or_create_customer(voter_phone, "Покупатель")
                    if voter_id == customer_id:
                        continue
                    await uow.review_votes.set_vote(tenant_id, review.id, voter_id, -1)
                await uow.commit()

    print(f"    Отзывов создано для товара id={product_id}: {count}")


async def _seed_reviews(tenant_id: int, product_ids: list[int], spec: ShopSpec) -> None:
    if spec.slug != "demo-market" or len(product_ids) < 4:
        return
    # 3 товара с 5-20 отзывами, 1 товар ровно с 1 отзывом, остальные — 0
    heavy_targets = [
        (product_ids[0], 20),
        (product_ids[3], 12),
        (product_ids[6], 5),
    ]
    for product_id, count in heavy_targets:
        await _seed_reviews_for_product(tenant_id, product_id, count)
    await _seed_reviews_for_product(tenant_id, product_ids[9], 1)


async def _seed_banners() -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        existing = await uow.platform_banners.list_all()
    existing_titles = {b.title for b in existing}

    banners = [
        BannerFields(
            placement="hero",
            title="Скидки до [50%] на электронику",
            subtitle="Успейте купить по низким ценам — акция ограничена по времени",
            button_text="Смотреть товары",
            link="/marketplace?with_discount=true",
            theme="accent",
            sort_order=1,
        ),
        BannerFields(
            placement="hero",
            title="Новые магазины на платформе",
            subtitle="Уже больше 30 проверенных продавцов в вашем городе",
            button_text="Все магазины",
            link="/marketplace/shops",
            theme="light",
            sort_order=2,
        ),
        BannerFields(
            placement="promo",
            title="Одежда [и обувь]",
            subtitle="Собери гардероб на сезон",
            button_text="Перейти",
            link="/marketplace?platform_category=clothing",
            theme="light",
            sort_order=1,
        ),
        BannerFields(
            placement="promo",
            title="Товары для дома",
            subtitle="Уют в каждой детали",
            button_text="Перейти",
            link="/marketplace?platform_category=home",
            theme="dark",
            sort_order=2,
        ),
    ]
    created = 0
    for fields in banners:
        if fields.title in existing_titles:
            continue
        banner = await create_platform_banner(SessionLocal, None, fields)
        source = RNG.choice(SOURCE_IMAGES)
        await set_platform_banner_image(
            SessionLocal, None, storage, banner.id, source.name, source.read_bytes()
        )
        created += 1
    print(f"  Баннеров создано: {created} (уже было: {len(existing_titles)})")


async def seed(force: bool) -> None:
    if not force:
        raise SystemExit(
            "Это dev-скрипт демо-данных, требует явного подтверждения — "
            "запустите с флагом --yes. НЕ запускать на продакшене."
        )

    print("=== Магазины ===")
    tenant_product_ids: dict[str, list[int]] = {}
    for spec in SHOPS:
        tenant_id, actor = await _get_or_create_tenant(spec)
        await _configure_shop(tenant_id, actor, spec)

        category_ids = await _get_or_create_categories(tenant_id, actor, spec.slug)

        async with SqlAlchemyUnitOfWork(tenant_id) as u:
            warehouses = await u.warehouses.list()
        warehouse_id = next(w.id for w in warehouses if w.show_on_storefront)

        print(f"  Товары «{spec.shop_name}»:")
        product_ids = await _seed_products(tenant_id, actor, spec, category_ids, warehouse_id)
        tenant_product_ids[spec.slug] = product_ids

        await _generate_sales(tenant_id, actor, spec, warehouse_id, product_ids)
        await _seed_reviews(tenant_id, product_ids, spec)

    print("=== Баннеры платформы ===")
    await _seed_banners()

    total_products = sum(len(ids) for ids in tenant_product_ids.values())
    print(f"\nГотово. Магазинов: {len(SHOPS)}, товаров суммарно: {total_products}.")
    for slug, ids in tenant_product_ids.items():
        print(f"  {slug}: {len(ids)} товаров, первые id: {ids[:5]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="подтвердить запуск (обязательно)")
    args = parser.parse_args()
    if not args.yes:
        print(
            "ВНИМАНИЕ: dev-only скрипт демо-данных. Запустите с --yes для подтверждения.",
            file=sys.stderr,
        )
        sys.exit(1)
    asyncio.run(seed(force=True))
