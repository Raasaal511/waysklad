from decimal import Decimal

from app.domain.common.uow import IUnitOfWork
from app.domain.storefront.entities import StorefrontRequest

# кандидат на авто-освобождение резерва — NEW-заявка старше этого возраста
# (см. release_expired_storefront_reservations и scheduler.py)
RESERVATION_TTL_HOURS = 72


async def reserve_request_stock(
    uow: IUnitOfWork, lines, visible_warehouse_ids: set[int]
) -> bool:
    """Резервирует каждую позицию заявки, по возможности жадно распределяя её
    между видимыми складами по id — заявка ещё не привязана к складу (его
    выбирает владелец при принятии), поэтому резерв ставится «где есть остаток»,
    а не на одном конкретном складе. Возвращает True, если резерв полностью
    покрыл запрошенное количество по каждой строке."""
    if not visible_warehouse_ids:
        return False

    warehouse_ids = sorted(visible_warehouse_ids)
    fully_covered = True
    for line in lines:
        remaining = line.quantity
        for warehouse_id in warehouse_ids:
            if remaining <= Decimal("0"):
                break
            on_hand = await uow.stock.get(line.product_id, warehouse_id, line.variant_id)
            reserved = await uow.stock.get_reserved(line.product_id, warehouse_id, line.variant_id)
            available = on_hand - reserved
            if available <= Decimal("0"):
                continue
            take = min(remaining, available)
            await uow.stock.reserve(line.product_id, warehouse_id, take, line.variant_id)
            remaining -= take
        if remaining > Decimal("0"):
            fully_covered = False
    return fully_covered


async def release_request_reservation(uow: IUnitOfWork, request: StorefrontRequest) -> None:
    """Снимает резерв заявки со всех видимых складов — симметрично
    reserve_request_stock: он не помнит, на каком складе резервировал сколько,
    поэтому release пробует снять по каждой строке с каждого видимого склада,
    пока не наберёт полное количество строки (get_reserved подсказывает, где
    реально что-то ещё зарезервировано)."""
    visible_warehouse_ids = sorted(w.id for w in await uow.warehouses.list() if w.show_on_storefront)
    for line in request.lines:
        remaining = line.quantity
        for warehouse_id in visible_warehouse_ids:
            if remaining <= Decimal("0"):
                break
            reserved = await uow.stock.get_reserved(line.product_id, warehouse_id, line.variant_id)
            if reserved <= Decimal("0"):
                continue
            give_back = min(remaining, reserved)
            await uow.stock.reserve(line.product_id, warehouse_id, -give_back, line.variant_id)
            remaining -= give_back
