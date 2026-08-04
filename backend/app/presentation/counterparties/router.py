from fastapi import APIRouter

from app.presentation.counterparties.schemas import (
    ClientCreateRequest,
    ClientResponse,
    SupplierCreateRequest,
    SupplierResponse,
)
from app.presentation.deps import ActorDep, CreateClientDep, CreateSupplierDep, UowDep

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


@router.post("/clients", status_code=201)
async def create_client(
    body: ClientCreateRequest, actor: ActorDep, use_case: CreateClientDep
) -> ClientResponse:
    return ClientResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/clients")
async def search_clients(uow: UowDep, query: str = "") -> list[ClientResponse]:
    async with uow:
        return [ClientResponse.from_entity(c) for c in await uow.clients.search(query)]


@router.post("/suppliers", status_code=201)
async def create_supplier(
    body: SupplierCreateRequest, actor: ActorDep, use_case: CreateSupplierDep
) -> SupplierResponse:
    return SupplierResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/suppliers")
async def list_suppliers(uow: UowDep) -> list[SupplierResponse]:
    async with uow:
        return [SupplierResponse.from_entity(s) for s in await uow.suppliers.list()]
