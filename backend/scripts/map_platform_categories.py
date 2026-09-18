"""Одноразовое автосопоставление существующих категорий магазинов со справочником
категорий платформы — по нормализованному названию и словарю синонимов
(app.domain.platform.category_synonyms). Несопоставленные категории остаются
platform_category_id=null (владелец при желании сопоставит вручную).

Уже сопоставленные категории (platform_category_id уже задан) пропускаются —
скрипт безопасно перезапускать.

Запуск (один раз, после миграции platform_categories):
    docker compose exec backend python -m scripts.map_platform_categories
"""

import asyncio

from app.domain.catalog.entities import Category
from app.domain.platform.category_synonyms import match_platform_slug
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def _platform_slug_to_id(uow: SqlAlchemyUnitOfWork) -> dict[str, int]:
    categories = await uow.platform_categories.list_all()
    return {c.slug: c.id for c in categories}


async def map_categories() -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()
        slug_to_id = await _platform_slug_to_id(uow)

    if not slug_to_id:
        print("Справочник platform_categories пуст — сначала примените сид-миграцию.")
        return

    matched = 0
    skipped_already_mapped = 0
    unmatched: list[str] = []

    for tenant in tenants:
        async with SqlAlchemyUnitOfWork(tenant.id) as uow:
            categories = await uow.categories.list()
            tenant_matched = 0
            for category in categories:
                if category.platform_category_id is not None:
                    skipped_already_mapped += 1
                    continue
                slug = match_platform_slug(category.name)
                if slug is None:
                    unmatched.append(f"«{category.name}» (магазин «{tenant.name}»)")
                    continue
                platform_category_id = slug_to_id.get(slug)
                if platform_category_id is None:
                    continue
                updated = Category(
                    id=category.id,
                    name=category.name,
                    parent_id=category.parent_id,
                    platform_category_id=platform_category_id,
                )
                await uow.categories.save(updated)
                tenant_matched += 1
            if tenant_matched:
                await uow.commit()
                matched += tenant_matched
                print(f"  «{tenant.name}» (tenant_id={tenant.id}): сопоставлено {tenant_matched}")

    print(f"\nГотово. Сопоставлено: {matched}. Уже было сопоставлено: {skipped_already_mapped}.")
    if unmatched:
        print(f"Не сопоставлено ({len(unmatched)}), platform_category_id остался null:")
        for name in unmatched:
            print(f"  - {name}")


if __name__ == "__main__":
    asyncio.run(map_categories())
