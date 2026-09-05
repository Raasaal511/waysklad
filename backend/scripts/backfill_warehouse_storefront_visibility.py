"""Одноразовый backfill для TECH_DEBT #23: миграция warehouses.show_on_storefront
(дефолт false) сделала все склады невидимыми на витрине разом — у магазинов,
где витрина уже была включена ДО сессии 27, товары внезапно показали
in_stock: false. Включает show_on_storefront=True на всех складах тех
тенантов, у которых storefront_enabled=True — восстанавливает поведение
«витрина показывает всё, как раньше» без ручного похода владельца в
настройки каждого склада.

Запуск (один раз, перед деплоем на окружение с уже существующими магазинами,
у которых витрина включена):
    docker compose exec backend python -m scripts.backfill_warehouse_storefront_visibility
"""

import asyncio

from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def backfill() -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()
    storefront_tenants = [t for t in tenants if t.storefront_enabled]

    if not storefront_tenants:
        print("Нет магазинов с включённой витриной — ничего делать не нужно.")
        return

    updated = 0
    for tenant in storefront_tenants:
        async with SqlAlchemyUnitOfWork(tenant.id) as uow:
            warehouses = await uow.warehouses.list()
            tenant_updated = 0
            for warehouse in warehouses:
                if warehouse.show_on_storefront:
                    continue
                await uow.warehouses.update_details(
                    warehouse.id, warehouse.name, warehouse.address, show_on_storefront=True
                )
                tenant_updated += 1
            await uow.commit()
            updated += tenant_updated
        print(f"  «{tenant.name}» (tenant_id={tenant.id}): {tenant_updated} склад(ов) включено")

    print(f"Готово. Обновлено складов: {updated}.")


if __name__ == "__main__":
    asyncio.run(backfill())
