from fastapi import APIRouter

from app.application.counterparties.get_client_summary import GetClientSummaryCommand
from app.application.counterparties.get_client_timeline import GetClientTimelineCommand
from app.presentation.counterparties.schemas import (
    ClientCreateRequest,
    ClientResponse,
    ClientSummaryResponse,
    ClientTimelineEventResponse,
    ClientUpdateRequest,
    SupplierCreateRequest,
    SupplierResponse,
)
from app.presentation.deps import (
    ActorDep,
    CreateClientDep,
    CreateSupplierDep,
    GetClientSummaryDep,
    GetClientTimelineDep,
    UowDep,
    UpdateClientDep,
)

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


@router.post("/clients", status_code=201)
async def create_client(
    body: ClientCreateRequest, actor: ActorDep, use_case: CreateClientDep
) -> ClientResponse:
    return ClientResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/clients")
async def search_clients(
    uow: UowDep, actor: ActorDep, query: str = "", include_inactive: bool = False
) -> list[ClientResponse]:
    async with uow:
        warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
        clients = await uow.clients.search(
            query, include_inactive=include_inactive, warehouse_ids=warehouse_ids
        )
        return [ClientResponse.from_entity(c) for c in clients]


@router.patch("/clients/{client_id}")
async def update_client(
    client_id: int, body: ClientUpdateRequest, actor: ActorDep, use_case: UpdateClientDep
) -> ClientResponse:
    client = await use_case.execute(actor, body.to_command(client_id))
    return ClientResponse.from_entity(client)


@router.get("/clients/{client_id}")
async def get_client_summary(
    client_id: int, actor: ActorDep, use_case: GetClientSummaryDep
) -> ClientSummaryResponse:
    summary = await use_case.execute(actor, GetClientSummaryCommand(client_id=client_id))
    return ClientSummaryResponse.from_summary(summary)


@router.get("/clients/{client_id}/timeline")
async def get_client_timeline(
    client_id: int, actor: ActorDep, use_case: GetClientTimelineDep
) -> list[ClientTimelineEventResponse]:
    events = await use_case.execute(actor, GetClientTimelineCommand(client_id=client_id))
    return [ClientTimelineEventResponse.from_entity(e) for e in events]


@router.post("/suppliers", status_code=201)
async def create_supplier(
    body: SupplierCreateRequest, actor: ActorDep, use_case: CreateSupplierDep
) -> SupplierResponse:
    return SupplierResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/suppliers")
async def list_suppliers(uow: UowDep, actor: ActorDep) -> list[SupplierResponse]:
    async with uow:
        warehouse_ids = actor.warehouse_ids if actor.is_warehouse_scoped else None
        suppliers = await uow.suppliers.list(warehouse_ids=warehouse_ids)
        return [SupplierResponse.from_entity(s) for s in suppliers]
