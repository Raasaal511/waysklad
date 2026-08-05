from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Iterator

import openpyxl

from app.application.products.create_product import CreateProductCommand, CreateProductUseCase
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require

# порядок колонок после заголовка (строка 1 листа пропускается):
# Название | Артикул | Штрихкод | Ед. изм. | Закупочная цена | Розничная цена | Мин. остаток
_ROW_LENGTH = 7


@dataclass(frozen=True)
class ImportProductsCommand:
    file_bytes: bytes


@dataclass(frozen=True)
class RowError:
    row: int
    message: str


@dataclass(frozen=True)
class ImportProductsResult:
    created: int
    errors: list[RowError] = field(default_factory=list)


class ImportProductsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ImportProductsCommand) -> ImportProductsResult:
        require(actor, Permission.PRODUCTS_MANAGE)

        create_product = CreateProductUseCase(self._uow)
        created = 0
        errors: list[RowError] = []
        for row_number, row in self._read_rows(cmd.file_bytes):
            try:
                await create_product.execute(actor, self._row_to_command(row))
                created += 1
            except (DomainError, ValueError, TypeError, InvalidOperation) as exc:
                errors.append(RowError(row_number, str(exc)))

        async with self._uow as uow:
            await uow.audit.add(
                AuditEntry.record(
                    actor, "product.import", None, created=created, errors=len(errors)
                )
            )
            await uow.commit()
        return ImportProductsResult(created=created, errors=errors)

    @staticmethod
    def _read_rows(file_bytes: bytes) -> Iterator[tuple[int, tuple]]:
        workbook = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        try:
            sheet = workbook.active
            for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                if row and row[0]:
                    yield row_number, row
        finally:
            workbook.close()

    @staticmethod
    def _row_to_command(row: tuple) -> CreateProductCommand:
        name, sku, barcode, unit_code, purchase_price, retail_price, min_stock = (
            tuple(row) + (None,) * _ROW_LENGTH
        )[:_ROW_LENGTH]
        return CreateProductCommand(
            name=str(name).strip(),
            unit_code=str(unit_code).strip() if unit_code else "pcs",
            purchase_price=Decimal(str(purchase_price)),
            retail_price=Decimal(str(retail_price)),
            sku=str(sku).strip() if sku else "",
            barcode=str(barcode).strip() if barcode else None,
            min_stock=Decimal(str(min_stock)) if min_stock not in (None, "") else Decimal("0"),
        )
