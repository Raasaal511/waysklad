import secrets
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone
from app.domain.storefront.entities import StorefrontRequest, StorefrontRequestLine
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class StorefrontRequestItemInput:
    product_id: int
    quantity: Decimal
    variant_id: int | None = None


@dataclass(frozen=True)
class CreateStorefrontRequestCommand:
    slug: str
    customer_name: str
    items: list[StorefrontRequestItemInput] = field(default_factory=list)
    customer_phone: str = ""
    note: str = ""


class CreateStorefrontRequestUseCase:
    """Публичная (без авторизации) заявка с витрины — лёгкая, без резерва остатка
    и без даты готовности. Становится Order только когда владелец её примет."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: CreateStorefrontRequestCommand) -> StorefrontRequest | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
        if tenant is None or not tenant.storefront_enabled:
            return None

        phone = Phone(cmd.customer_phone) if cmd.customer_phone.strip() else None

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            for item in cmd.items:
                product = await uow.products.get(item.product_id)
                if not product.show_on_storefront:
                    raise DomainError(f"Товар «{product.name}» недоступен на витрине")

            request = StorefrontRequest(
                id=None,
                customer_name=cmd.customer_name.strip(),
                customer_phone=str(phone) if phone else "",
                note=cmd.note.strip(),
                access_token=secrets.token_urlsafe(32),
                lines=[
                    StorefrontRequestLine(
                        product_id=item.product_id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                    )
                    for item in cmd.items
                ],
            )
            request.validate()
            await uow.storefront_requests.add(request)
            await uow.commit()
            return request
