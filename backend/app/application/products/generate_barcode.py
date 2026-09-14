import random
from dataclasses import dataclass

from app.domain.catalog.barcode import Barcode
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require

_MAX_ATTEMPTS = 20


@dataclass(frozen=True)
class GenerateBarcodeResult:
    barcode: str


def _ean13_check_digit(digits: str) -> int:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return (10 - total % 10) % 10


def _random_ean13() -> Barcode:
    # 200-299 — диапазон GS1 "restricted circulation" для внутреннего использования
    # магазином (не привязан к реальному производителю), тот же смысл, что
    # у штрихкодов собственной генерации в кассовом ПО
    body = "2" + "".join(str(random.randint(0, 9)) for _ in range(11))
    return Barcode(body + str(_ean13_check_digit(body)))


class GenerateBarcodeUseCase:
    """Только предлагает уникальный (в пределах магазина) штрихкод — ничего не
    сохраняет. Применяется тем же PUT/POST /products, куда владелец сам впишет
    предложенное значение."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor) -> GenerateBarcodeResult:
        require(actor, Permission.PRODUCTS_MANAGE)

        async with self._uow as uow:
            for _ in range(_MAX_ATTEMPTS):
                candidate = _random_ean13()
                existing = await uow.products.get_by_barcode(candidate)
                if existing is None:
                    return GenerateBarcodeResult(barcode=candidate.value)

        raise DomainError("Не удалось подобрать свободный штрихкод, попробуйте ещё раз")
