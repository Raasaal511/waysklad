from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Response

from app.application.sales.delete_sale import DeleteSaleCommand
from app.application.sales.get_sales_summary import GetSalesSummaryCommand
from app.application.sales.list_sales import ListSalesCommand
from app.domain.identity.permissions import Permission, require_warehouse
from app.domain.sales.payment import PaymentMethod
from app.domain.sales.receipt import build_whatsapp_link, render_receipt_text
from app.infrastructure.export.receipt_pdf import render_receipt_pdf
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.deps import (
    ActorDep,
    CreateSaleDep,
    DeleteSaleDep,
    EditSaleDep,
    GetReceiptDataDep,
    GetSaleDep,
    GetSaleHistoryDep,
    GetSalesSummaryDep,
    ListSaleReturnsDep,
    ListSalesDep,
    ReturnSaleDep,
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
    SalesSummaryResponse,
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
async def list_sales(
    response: Response,
    actor: ActorDep,
    use_case: ListSalesDep,
    limit: int = 50,
    offset: int = 0,
    client_id: int | None = None,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    payment_method: PaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "date_desc",
) -> list[SaleResponse]:
    result = await use_case.execute(
        actor,
        ListSalesCommand(
            limit=limit,
            offset=offset,
            client_id=client_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            payment_method=payment_method,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
        ),
    )
    response.headers["X-Total-Count"] = str(result.total)
    return [SaleResponse.from_entity(s) for s in result.sales]


@router.get("/summary", dependencies=[require_permission(Permission.SALES_CREATE)])
async def get_sales_summary(
    actor: ActorDep,
    use_case: GetSalesSummaryDep,
    warehouse_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> SalesSummaryResponse:
    stats = await use_case.execute(
        actor, GetSalesSummaryCommand(warehouse_id=warehouse_id, date_from=date_from, date_to=date_to)
    )
    return SalesSummaryResponse.from_stats(stats)


@router.get("/{sale_id}", dependencies=[require_permission(Permission.SALES_CREATE)])
async def get_sale(sale_id: int, actor: ActorDep, use_case: GetSaleDep) -> SaleResponse:
    return SaleResponse.from_entity(await use_case.execute(actor, sale_id))


@router.patch("/{sale_id}", dependencies=[require_permission(Permission.SALES_EDIT)])
async def edit_sale(
    sale_id: int,
    body: SaleEditRequest,
    actor: ActorDep,
    use_case: EditSaleDep,
    get_sale_use_case: GetSaleDep,
) -> SaleResponse:
    await use_case.execute(actor, body.to_command(sale_id))
    return SaleResponse.from_entity(await get_sale_use_case.execute(actor, sale_id))


@router.delete(
    "/{sale_id}", status_code=204, dependencies=[require_permission(Permission.SALES_DELETE)]
)
async def delete_sale(sale_id: int, actor: ActorDep, use_case: DeleteSaleDep) -> None:
    await use_case.execute(actor, DeleteSaleCommand(sale_id=sale_id))


@router.get(
    "/{sale_id}/history", dependencies=[require_permission(Permission.SALES_CREATE)]
)
async def get_sale_history(
    sale_id: int, actor: ActorDep, use_case: GetSaleHistoryDep
) -> list[AuditEntryResponse]:
    entries = await use_case.execute(actor, sale_id)
    return [AuditEntryResponse.from_entity(e) for e in entries]


@router.get(
    "/{sale_id}/returns", dependencies=[require_permission(Permission.SALES_CREATE)]
)
async def list_sale_returns(
    sale_id: int, actor: ActorDep, use_case: ListSaleReturnsDep
) -> list[SaleReturnResponse]:
    returns, price_by_line = await use_case.execute(actor, sale_id)
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


@router.get("/{sale_id}/receipt", dependencies=[require_permission(Permission.SALES_CREATE)])
async def get_receipt(sale_id: int, actor: ActorDep, use_case: GetReceiptDataDep) -> ReceiptResponse:
    data = await use_case.execute(sale_id)
    require_warehouse(actor, data.sale.warehouse_id)
    text = render_receipt_text(
        data.tenant.name, data.sale, data.product_names, data.client.name if data.client else None
    )
    phone = (data.client.whatsapp or data.client.phone) if data.client else None
    return ReceiptResponse(text=text, whatsapp_link=build_whatsapp_link(phone, text) if phone else None)


@router.get(
    "/{sale_id}/receipt.pdf", dependencies=[require_permission(Permission.SALES_CREATE)]
)
async def get_receipt_pdf(sale_id: int, actor: ActorDep, use_case: GetReceiptDataDep) -> Response:
    data = await use_case.execute(sale_id)
    require_warehouse(actor, data.sale.warehouse_id)
    pdf_bytes = render_receipt_pdf(
        data.tenant.name, data.sale, data.product_names, data.client.name if data.client else None
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="chek-{data.sale.id}.pdf"'},
    )
