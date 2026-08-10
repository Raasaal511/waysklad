from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.inventory.common import LineInput
from app.application.inventory.create_warehouse import CreateWarehouseCommand
from app.application.inventory.receive_goods import ReceiveGoodsCommand
from app.application.inventory.set_warehouse_assignments import SetWarehouseAssignmentsCommand
from app.application.inventory.stocktake import StocktakeCommand, StocktakeResult
from app.application.inventory.transfer import TransferCommand
from app.application.inventory.write_off import WriteOffCommand
from app.domain.identity.entities import Warehouse
from app.domain.inventory.entities import StockDocType, StockDocument, StockItem


class LineRequest(BaseModel):
    product_id: int
    quantity: Decimal
    variant_id: int | None = None
    cost: Decimal | None = None  # закупочная (для приёмки)

    def to_input(self) -> LineInput:
        return LineInput(
            product_id=self.product_id,
            quantity=self.quantity,
            variant_id=self.variant_id,
            cost=self.cost,
        )


class _DocumentRequest(BaseModel):
    warehouse_id: int
    lines: list[LineRequest]
    note: str = ""

    def _lines(self) -> list[LineInput]:
        return [line.to_input() for line in self.lines]


class ReceiveRequest(_DocumentRequest):
    def to_command(self) -> ReceiveGoodsCommand:
        return ReceiveGoodsCommand(
            warehouse_id=self.warehouse_id, lines=self._lines(), note=self.note
        )


class WriteOffRequest(_DocumentRequest):
    def to_command(self) -> WriteOffCommand:
        return WriteOffCommand(
            warehouse_id=self.warehouse_id, lines=self._lines(), note=self.note
        )


class TransferRequest(_DocumentRequest):
    to_warehouse_id: int

    def to_command(self) -> TransferCommand:
        return TransferCommand(
            warehouse_id=self.warehouse_id,
            to_warehouse_id=self.to_warehouse_id,
            lines=self._lines(),
            note=self.note,
        )


class StocktakeRequest(_DocumentRequest):
    # lines.quantity = фактический остаток после пересчёта
    def to_command(self) -> StocktakeCommand:
        return StocktakeCommand(
            warehouse_id=self.warehouse_id, lines=self._lines(), note=self.note
        )


class WarehouseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = ""
    assigned_user_ids: list[int] = Field(default_factory=list)

    def to_command(self) -> CreateWarehouseCommand:
        return CreateWarehouseCommand(
            name=self.name, address=self.address, assigned_user_ids=self.assigned_user_ids
        )


class WarehouseAssignmentsRequest(BaseModel):
    user_ids: list[int] = Field(default_factory=list)

    def to_command(self, warehouse_id: int) -> SetWarehouseAssignmentsCommand:
        return SetWarehouseAssignmentsCommand(warehouse_id=warehouse_id, user_ids=self.user_ids)


class WarehouseResponse(BaseModel):
    id: int
    name: str
    address: str
    assigned_user_ids: list[int]

    @classmethod
    def from_entity(cls, warehouse: Warehouse) -> "WarehouseResponse":
        return cls(
            id=warehouse.id, name=warehouse.name, address=warehouse.address,
            assigned_user_ids=warehouse.assigned_user_ids,
        )


class StockItemResponse(BaseModel):
    product_id: int
    variant_id: int | None
    warehouse_id: int
    quantity: Decimal

    @classmethod
    def from_entity(cls, item: StockItem) -> "StockItemResponse":
        return cls(
            product_id=item.product_id, variant_id=item.variant_id,
            warehouse_id=item.warehouse_id, quantity=item.quantity,
        )


class DocumentResponse(BaseModel):
    id: int
    type: StockDocType
    warehouse_id: int
    to_warehouse_id: int | None
    note: str

    @classmethod
    def from_entity(cls, document: StockDocument) -> "DocumentResponse":
        return cls(
            id=document.id,
            type=document.type,
            warehouse_id=document.warehouse_id,
            to_warehouse_id=document.to_warehouse_id,
            note=document.note,
        )


class DiscrepancyResponse(BaseModel):
    product_id: int
    variant_id: int | None
    expected: Decimal
    actual: Decimal
    delta: Decimal


class StocktakeResponse(BaseModel):
    document: DocumentResponse
    discrepancies: list[DiscrepancyResponse]

    @classmethod
    def from_result(cls, result: StocktakeResult) -> "StocktakeResponse":
        return cls(
            document=DocumentResponse.from_entity(result.document),
            discrepancies=[
                DiscrepancyResponse(
                    product_id=d.product_id,
                    variant_id=d.variant_id,
                    expected=d.expected,
                    actual=d.actual,
                    delta=d.delta,
                )
                for d in result.discrepancies
            ],
        )
