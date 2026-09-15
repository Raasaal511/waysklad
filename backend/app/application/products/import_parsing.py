import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Iterator, Literal

import openpyxl

from app.domain.common.quantity import UNITS

# порядок колонок после заголовка (первая строка пропускается) — совпадает с
# порядком, в котором products_export.py выгружает файл, чтобы экспортированный
# файл можно было импортировать обратно без ручной правки:
# Название | Артикул | Штрихкод | Ед.изм. | Категория | Закупочная цена |
# Розничная цена | Маржа (игнорируется, вычисляется) | Мин.остаток
_ROW_LENGTH = 9

_UNIT_CODE_BY_NAME = {u.name.strip().casefold(): u.code for u in UNITS.values()}

ImportFormat = Literal["xlsx", "csv"]


@dataclass(frozen=True)
class ParsedRow:
    row: int
    name: str
    sku: str
    barcode: str | None
    unit_code: str
    category_name: str | None
    purchase_price: Decimal | None
    retail_price: Decimal | None
    min_stock: Decimal
    parse_error: str | None


def parse_import_rows(file_bytes: bytes, file_format: ImportFormat) -> list[ParsedRow]:
    raw_rows = _read_csv_rows(file_bytes) if file_format == "csv" else _read_xlsx_rows(file_bytes)
    return [_parse_row(row_number, row) for row_number, row in raw_rows]


def _read_xlsx_rows(file_bytes: bytes) -> Iterator[tuple[int, tuple]]:
    workbook = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if row and row[0]:
                yield row_number, row
    finally:
        workbook.close()


def _read_csv_rows(file_bytes: bytes) -> Iterator[tuple[int, tuple]]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    for row_number, row in enumerate(reader, start=1):
        if row_number == 1:
            continue  # заголовок
        if row and row[0]:
            yield row_number, tuple(row)


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    return Decimal(text)


def _resolve_unit_code(raw: object) -> str:
    """Принимает и код ('pcs'), и русское название единицы ('шт') — так файл,
    экспортированный этой же системой (где пишется unit.name), импортируется обратно
    без ручной правки колонки. Нераспознанное значение возвращается как есть —
    ошибка "Неизвестная единица измерения" будет понятной на шаге создания товара."""
    text = str(raw).strip() if raw else ""
    if not text:
        return "pcs"
    if text in UNITS:
        return text
    return _UNIT_CODE_BY_NAME.get(text.casefold(), text)


def _parse_row(row_number: int, row: tuple) -> ParsedRow:
    (
        name,
        sku,
        barcode,
        unit_code,
        category_name,
        purchase_price,
        retail_price,
        _margin,
        min_stock,
    ) = (tuple(row) + (None,) * _ROW_LENGTH)[:_ROW_LENGTH]
    name_str = str(name).strip() if name else ""
    error: str | None = None
    parsed_purchase: Decimal | None = None
    parsed_retail: Decimal | None = None
    parsed_min_stock = Decimal("0")
    if not name_str:
        error = "Не указано название"
    else:
        try:
            parsed_purchase = _parse_decimal(purchase_price)
            parsed_retail = _parse_decimal(retail_price)
            parsed_min_stock = _parse_decimal(min_stock) or Decimal("0")
        except (InvalidOperation, ValueError, TypeError):
            error = "Некорректное числовое значение в цене или остатке"
    category_str = str(category_name).strip() if category_name else None
    return ParsedRow(
        row=row_number,
        name=name_str,
        sku=str(sku).strip() if sku else "",
        barcode=str(barcode).strip() if barcode else None,
        unit_code=_resolve_unit_code(unit_code),
        category_name=category_str or None,
        purchase_price=parsed_purchase,
        retail_price=parsed_retail,
        min_stock=parsed_min_stock,
        parse_error=error,
    )
