from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.application.counterparties.create_client import CreateClientCommand
from app.application.counterparties.create_supplier import CreateSupplierCommand
from app.application.counterparties.get_client_summary import ClientSummary
from app.application.counterparties.update_client import UpdateClientCommand
from app.domain.counterparties.entities import Client, Supplier
from app.domain.counterparties.timeline import ClientTimelineEvent, TimelineEventType


class ClientCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = ""
    whatsapp: str = ""
    city: str = ""
    debt_limit: Decimal | None = None

    def to_command(self) -> CreateClientCommand:
        return CreateClientCommand(
            name=self.name,
            phone=self.phone,
            whatsapp=self.whatsapp,
            city=self.city,
            debt_limit=self.debt_limit,
        )


class ClientUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = ""
    whatsapp: str = ""
    city: str = ""
    debt_limit: Decimal | None = None
    is_active: bool = True
    force: bool = False  # подтвердить деактивацию клиента с непогашенным долгом

    def to_command(self, client_id: int) -> UpdateClientCommand:
        return UpdateClientCommand(
            client_id=client_id,
            name=self.name,
            phone=self.phone,
            whatsapp=self.whatsapp,
            city=self.city,
            debt_limit=self.debt_limit,
            is_active=self.is_active,
            force=self.force,
        )


class ClientResponse(BaseModel):
    id: int
    name: str
    phone: str
    whatsapp: str
    city: str
    debt_limit: Decimal | None
    is_active: bool = True

    @classmethod
    def from_entity(cls, client: Client) -> "ClientResponse":
        return cls(
            id=client.id,
            name=client.name,
            phone=str(client.phone) if client.phone else "",
            whatsapp=str(client.whatsapp) if client.whatsapp else "",
            city=client.city,
            debt_limit=client.debt_limit.amount if client.debt_limit else None,
            is_active=client.is_active,
        )


class ClientSummaryResponse(BaseModel):
    client: ClientResponse
    debt_balance: Decimal
    active_orders_count: int
    open_tasks_count: int

    @classmethod
    def from_summary(cls, summary: ClientSummary) -> "ClientSummaryResponse":
        return cls(
            client=ClientResponse.from_entity(summary.client),
            debt_balance=summary.debt_balance.amount,
            active_orders_count=summary.active_orders_count,
            open_tasks_count=summary.open_tasks_count,
        )


class ClientTimelineEventResponse(BaseModel):
    type: TimelineEventType
    occurred_at: datetime
    entity_id: int
    title: str
    amount: Decimal | None
    status: str | None

    @classmethod
    def from_entity(cls, event: ClientTimelineEvent) -> "ClientTimelineEventResponse":
        return cls(
            type=event.type,
            occurred_at=event.occurred_at,
            entity_id=event.entity_id,
            title=event.title,
            amount=event.amount.amount if event.amount else None,
            status=event.status,
        )


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact: str = ""
    note: str = ""

    def to_command(self) -> CreateSupplierCommand:
        return CreateSupplierCommand(name=self.name, contact=self.contact, note=self.note)


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact: str
    note: str

    @classmethod
    def from_entity(cls, supplier: Supplier) -> "SupplierResponse":
        return cls(
            id=supplier.id, name=supplier.name, contact=supplier.contact, note=supplier.note
        )
