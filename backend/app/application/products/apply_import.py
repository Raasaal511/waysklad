from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.application.products.create_product import CreateProductCommand, CreateProductUseCase
from app.application.products.update_product import UpdateProductCommand, UpdateProductUseCase
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require

ImportAction = Literal["create", "update", "skip"]


@dataclass(frozen=True)
class ApplyImportRow:
    client_row_id: str
    action: ImportAction
    name: str = ""
    sku: str = ""
    barcode: str | None = None
    unit_code: str = "pcs"
    purchase_price: Decimal = Decimal("0")
    retail_price: Decimal = Decimal("0")
    category_id: int | None = None
    min_stock: Decimal = Decimal("0")
    existing_product_id: int | None = None


@dataclass(frozen=True)
class ApplyImportCommand:
    rows: list[ApplyImportRow] = field(default_factory=list)


@dataclass(frozen=True)
class ApplyImportRowError:
    client_row_id: str
    message: str


@dataclass(frozen=True)
class ApplyImportResult:
    created: int
    updated: int
    skipped: int
    errors: list[ApplyImportRowError] = field(default_factory=list)


class ApplyProductImportUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: ApplyImportCommand) -> ApplyImportResult:
        require(actor, Permission.PRODUCTS_MANAGE)

        create_uc = CreateProductUseCase(self._uow)
        update_uc = UpdateProductUseCase(self._uow)
        created = updated = skipped = 0
        errors: list[ApplyImportRowError] = []

        for row in cmd.rows:
            if row.action == "skip":
                skipped += 1
                continue
            try:
                if row.action == "create":
                    await create_uc.execute(
                        actor,
                        CreateProductCommand(
                            name=row.name,
                            unit_code=row.unit_code,
                            purchase_price=row.purchase_price,
                            retail_price=row.retail_price,
                            sku=row.sku,
                            barcode=row.barcode,
                            category_id=row.category_id,
                            min_stock=row.min_stock,
                        ),
                    )
                    created += 1
                elif row.action == "update":
                    if row.existing_product_id is None:
                        raise DomainError("Не указан товар для обновления")
                    await update_uc.execute(
                        actor,
                        UpdateProductCommand(
                            product_id=row.existing_product_id,
                            name=row.name,
                            unit_code=row.unit_code,
                            purchase_price=row.purchase_price,
                            retail_price=row.retail_price,
                            sku=row.sku,
                            barcode=row.barcode,
                            category_id=row.category_id,
                            min_stock=row.min_stock,
                        ),
                    )
                    updated += 1
            except (DomainError, ValueError, TypeError) as exc:
                errors.append(ApplyImportRowError(row.client_row_id, str(exc)))

        async with self._uow as uow:
            await uow.audit.add(
                AuditEntry.record(
                    actor,
                    "product.import",
                    None,
                    created=created,
                    updated=updated,
                    skipped=skipped,
                    errors=len(errors),
                )
            )
            await uow.commit()
        return ApplyImportResult(created=created, updated=updated, skipped=skipped, errors=errors)
