from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.application.products.import_parsing import ImportFormat, parse_import_rows
from app.domain.catalog.entities import Product
from app.domain.catalog.repository import DuplicateLookupKey, DuplicateMatch
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require

MatchStatus = Literal["no_match", "match", "ambiguous_match"]

_MATCH_PRIORITY = {"barcode": 0, "sku": 1, "name": 2}


@dataclass(frozen=True)
class PreviewProductsCommand:
    file_bytes: bytes
    file_format: ImportFormat = "xlsx"


@dataclass(frozen=True)
class ExistingProductSnapshot:
    id: int
    name: str
    sku: str
    barcode: str | None
    unit_code: str
    purchase_price: Decimal
    retail_price: Decimal
    category_id: int | None
    min_stock: Decimal


@dataclass(frozen=True)
class DuplicateCandidate:
    matched_by: Literal["barcode", "sku", "name"]
    product: ExistingProductSnapshot


@dataclass(frozen=True)
class PreviewRow:
    row: int
    name: str
    sku: str
    barcode: str | None
    unit_code: str
    category_id: int | None
    purchase_price: Decimal | None
    retail_price: Decimal | None
    min_stock: Decimal
    parse_error: str | None
    status: MatchStatus
    candidates: list[DuplicateCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class PreviewProductsResult:
    rows: list[PreviewRow]


def _to_snapshot(product: Product) -> ExistingProductSnapshot:
    return ExistingProductSnapshot(
        id=product.id,
        name=product.name,
        sku=product.sku,
        barcode=product.barcode.value if product.barcode else None,
        unit_code=product.unit.code,
        purchase_price=product.purchase_price.amount,
        retail_price=product.retail_price.amount,
        category_id=product.category_id,
        min_stock=product.min_stock,
    )


class PreviewProductsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: PreviewProductsCommand) -> PreviewProductsResult:
        require(actor, Permission.PRODUCTS_MANAGE)

        parsed = parse_import_rows(cmd.file_bytes, cmd.file_format)

        async with self._uow as uow:
            lookup_keys = [
                DuplicateLookupKey(row_index=p.row, name=p.name, sku=p.sku, barcode=p.barcode)
                for p in parsed
                if p.parse_error is None
            ]
            raw_matches = await uow.products.find_duplicates(lookup_keys)
            categories = await uow.categories.list()

        category_id_by_name = {c.name.strip().casefold(): c.id for c in categories}

        matches_by_row: dict[int, list[DuplicateMatch]] = {}
        for m in raw_matches:
            matches_by_row.setdefault(m.row_index, []).append(m)

        rows: list[PreviewRow] = []
        for p in parsed:
            status, candidates = self._resolve_status(matches_by_row.get(p.row, []))
            category_id = (
                category_id_by_name.get(p.category_name.casefold()) if p.category_name else None
            )
            rows.append(
                PreviewRow(
                    row=p.row,
                    name=p.name,
                    sku=p.sku,
                    barcode=p.barcode,
                    unit_code=p.unit_code,
                    category_id=category_id,
                    purchase_price=p.purchase_price,
                    retail_price=p.retail_price,
                    min_stock=p.min_stock,
                    parse_error=p.parse_error,
                    status=status,
                    candidates=candidates,
                )
            )
        return PreviewProductsResult(rows=rows)

    @staticmethod
    def _resolve_status(
        row_matches: list[DuplicateMatch],
    ) -> tuple[MatchStatus, list[DuplicateCandidate]]:
        if not row_matches:
            return "no_match", []
        row_matches = sorted(row_matches, key=lambda m: _MATCH_PRIORITY[m.matched_by])
        distinct_ids = {m.product.id for m in row_matches}
        candidates = [
            DuplicateCandidate(matched_by=m.matched_by, product=_to_snapshot(m.product))
            for m in row_matches
        ]
        if len(distinct_ids) > 1:
            return "ambiguous_match", candidates
        return "match", [candidates[0]]
