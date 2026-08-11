from decimal import Decimal

from fastapi import APIRouter, Response

from app.application.sales.delete_sale import DeleteSaleCommand
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Permission
from app.domain.sales.receipt import build_whatsapp_link, render_receipt_text
from app.infrastructure.receipt_pdf import render_receipt_pdf
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.deps import (
    ActorDep,
    CreateSaleDep,
    DeleteSaleDep,
    EditSaleDep,
    ReturnSaleDep,
    UowDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.sales.schemas import (
    ReceiptResponse,
    SaleCreateRequest,
    SaleEditRequest,
    SaleReturnCreateRequest,
    SaleReturnLineResponse,
    SaleReturnResponse,
    SaleResponse,
)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("", status_code=201)
async def create_sale(
    body: SaleCreateRequest, actor: ActorDep, use_case: CreateSaleDep
) -> SaleResponse:
    return SaleResponse.from_result(await use_case.execute(actor, body.to_command()))


@router.post("/{sale_id}/returns", status_code=201)
async def return_sale(
    sale_id: int, body: SaleReturnCreateRequest, actor: ActorDep, use_case: ReturnSaleDep
) -> SaleReturnResponse:
    result = await use_case.execute(actor, body.to_command(sale_id))
    return SaleReturnResponse.from_result(result)


@router.get("", dependencies=[require_permission(Permission.SALES_CREATE)])
async def list_sales(uow: UowDep) -> list[SaleResponse]:
    async with uow:
        return [SaleResponse.from_entity(s) for s in await uow.sales.list()]


@router.get("/{sale_id}", dependencies=[require_permission(Permission.SALES_CREATE)])
async def get_sale(sale_id: int, uow: UowDep) -> SaleResponse:
    async with uow:
        return SaleResponse.from_entity(await uow.sales.get(sale_id))


@router.patch("/{sale_id}", dependencies=[require_permission(Permission.SALES_EDIT)])
async def edit_sale(
    sale_id: int, body: SaleEditRequest, actor: ActorDep, use_case: EditSaleDep, uow: UowDep
) -> SaleResponse:
    await use_case.execute(actor, body.to_command(sale_id))
    async with uow:
        return SaleResponse.from_entity(await uow.sales.get(sale_id))


@router.delete(
    "/{sale_id}", status_code=204, dependencies=[require_permission(Permission.SALES_DELETE)]
)
async def delete_sale(sale_id: int, actor: ActorDep, use_case: DeleteSaleDep) -> None:
    await use_case.execute(actor, DeleteSaleCommand(sale_id=sale_id))


@router.get(
    "/{sale_id}/history", dependencies=[require_permission(Permission.SALES_CREATE)]
)
async def get_sale_history(sale_id: int, uow: UowDep) -> list[AuditEntryResponse]:
    async with uow:
        entries = await uow.audit.list_by_entity("sale", sale_id)
        return [AuditEntryResponse.from_entity(e) for e in entries]


@router.get(
    "/{sale_id}/returns", dependencies=[require_permission(Permission.SALES_CREATE)]
)
async def list_sale_returns(sale_id: int, uow: UowDep) -> list[SaleReturnResponse]:
    async with uow:
        sale = await uow.sales.get(sale_id)
        price_by_line = {line.id: line.price.amount for line in sale.lines}
        returns = await uow.sale_returns.list_by_sale(sale_id)
        return [
            SaleReturnResponse(
                id=r.id,
                sale_id=r.sale_id,
                note=r.note,
                refund=sum(
                    (price_by_line.get(line.sale_line_id, Decimal("0")) * line.quantity.value
                     for line in r.lines),
                    Decimal("0"),
                ),
                created_at=r.created_at,
                lines=[
                    SaleReturnLineResponse(
                        sale_line_id=line.sale_line_id, quantity=line.quantity.value
                    )
                    for line in r.lines
                ],
            )
            for r in returns
        ]


async def _load_receipt_data(sale_id: int, uow: IUnitOfWork):
    async with uow:
        sale = await uow.sales.get(sale_id)
        tenant = await uow.tenants.get(uow.tenant_id)
        product_names = {
            product_id: (await uow.products.get(product_id)).name
            for product_id in {line.product_id for line in sale.lines}
        }
        client = await uow.clients.get(sale.client_id) if sale.client_id else None
    return sale, tenant, product_names, client


@router.get("/{sale_id}/receipt", dependencies=[require_permission(Permission.SALES_CREATE)])
async def get_receipt(sale_id: int, uow: UowDep) -> ReceiptResponse:
    sale, tenant, product_names, client = await _load_receipt_data(sale_id, uow)
    text = render_receipt_text(tenant.name, sale, product_names, client.name if client else None)
    phone = (client.whatsapp or client.phone) if client else None
    return ReceiptResponse(text=text, whatsapp_link=build_whatsapp_link(phone, text) if phone else None)


@router.get(
    "/{sale_id}/receipt.pdf", dependencies=[require_permission(Permission.SALES_CREATE)]
)
async def get_receipt_pdf(sale_id: int, uow: UowDep) -> Response:
    sale, tenant, product_names, client = await _load_receipt_data(sale_id, uow)
    pdf_bytes = render_receipt_pdf(tenant.name, sale, product_names, client.name if client else None)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="chek-{sale.id}.pdf"'},
    )
