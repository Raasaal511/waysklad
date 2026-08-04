from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.exceptions import InsufficientStockError
from app.domain.common.money import Money
from app.domain.common.quantity import Quantity
from app.domain.common.uow import IUnitOfWork
from app.domain.inventory.entities import StockLine


@dataclass(frozen=True)
class LineInput:
    product_id: int
    quantity: Decimal
    variant_id: int | None = None
    cost: Decimal | None = None  # закупочная цена (для приёмки)


async def build_lines(uow: IUnitOfWork, lines: list[LineInput]) -> list[StockLine]:
    """Единица измерения строки берётся из карточки товара."""
    result = []
    for line in lines:
        product = await uow.products.get(line.product_id)
        result.append(
            StockLine(
                product_id=line.product_id,
                variant_id=line.variant_id,
                quantity=Quantity(line.quantity, product.unit),
                cost=Money.of(line.cost) if line.cost is not None else None,
            )
        )
    return result


async def decrease_stock(
    uow: IUnitOfWork, warehouse_id: int, line: StockLine
) -> None:
    new_quantity = await uow.stock.change(
        line.product_id, warehouse_id, -line.quantity.value, line.variant_id
    )
    if new_quantity < 0:
        raise InsufficientStockError(
            f"Недостаточно остатка товара {line.product_id} на складе {warehouse_id}"
        )
