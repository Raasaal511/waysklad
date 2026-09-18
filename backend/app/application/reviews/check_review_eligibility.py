from dataclasses import dataclass
from typing import Literal

from app.domain.storefront.entities import StorefrontRequestStatus
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

EligibilityReason = Literal["ok", "no_purchase", "already_reviewed"]


@dataclass(frozen=True)
class CheckReviewEligibilityCommand:
    slug: str
    product_id: int
    customer_id: int


@dataclass(frozen=True)
class ReviewEligibilityResult:
    can_review: bool
    request_id: int | None
    reason: EligibilityReason


class CheckReviewEligibilityUseCase:
    """Может ли покупатель оставить отзыв на этот товар в этом магазине —
    самая свежая ACCEPTED-заявка этого покупателя в этом магазине с этим
    товаром, по которой ещё нет отзыва НА ЭТОТ товар (промпт B3 п.6). Список
    заявок покупателя уже отсортирован новые-сначала (см.
    IStorefrontRequestRepository.list_by_customer), берём первую подходящую."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: CheckReviewEligibilityCommand) -> ReviewEligibilityResult | None:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            tenant = await public_uow.tenants.get_by_slug(cmd.slug)
            if tenant is None or not tenant.storefront_enabled or tenant.is_suspended:
                return None
            my_requests = await public_uow.storefront_requests.list_by_customer(cmd.customer_id)

        candidates = [
            r
            for r in my_requests
            if r.tenant_id == tenant.id
            and r.status == StorefrontRequestStatus.ACCEPTED
            and any(line.product_id == cmd.product_id for line in r.lines)
        ]
        if not candidates:
            return ReviewEligibilityResult(can_review=False, request_id=None, reason="no_purchase")

        async with SqlAlchemyUnitOfWork(tenant.id, session_factory=self._session_factory) as uow:
            for request in candidates:  # новые сначала — первая заявка БЕЗ отзыва на товар и есть ответ
                already = await uow.reviews.exists_for_request(request.id, cmd.product_id)
                if not already:
                    return ReviewEligibilityResult(can_review=True, request_id=request.id, reason="ok")

        return ReviewEligibilityResult(can_review=False, request_id=None, reason="already_reviewed")
