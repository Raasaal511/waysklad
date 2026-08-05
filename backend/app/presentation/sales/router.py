from fastapi import APIRouter

from app.domain.common.uow import IUnitOfWork
from app.domain.sales.receipt import build_whatsapp_link, render_receipt_text
from app.presentation.deps import ActorDep, CreateSaleDep, ReturnSaleDep, UowDep
from app.presentation.sales.schemas import (
    ReceiptResponse,
    SaleCreateRequest,
    SaleReturnCreateRequest,
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


async def _build_receipt(sale_id: int, uow: IUnitOfWork) -> ReceiptResponse:
    async with uow:
        sale = await uow.sales.get(sale_id)
        tenant = await uow.tenants.get(uow.tenant_id)
        product_names = {
            product_id: (await uow.products.get(product_id)).name
            for product_id in {line.product_id for line in sale.lines}
        }
        client = await uow.clients.get(sale.client_id) if sale.client_id else None

    text = render_receipt_text(tenant.name, sale, product_names, client.name if client else None)
    phone = (client.whatsapp or client.phone) if client else None
    return ReceiptResponse(text=text, whatsapp_link=build_whatsapp_link(phone, text) if phone else None)


@router.get("/{sale_id}/receipt")
async def get_receipt(sale_id: int, uow: UowDep) -> ReceiptResponse:
    return await _build_receipt(sale_id, uow)
