from fastapi import APIRouter, HTTPException, Request

from app.application.reviews.list_product_reviews import ListProductReviewsCommand
from app.application.reviews.list_reviews_for_owner import ListReviewsForOwnerCommand
from app.application.reviews.set_review_hidden import SetReviewHiddenCommand
from app.domain.identity.permissions import Permission
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import (
    ActorDep,
    CreateReviewDep,
    ListProductReviewsDep,
    ListReviewsForOwnerDep,
    SetReviewHiddenDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.deps.customer_auth import CurrentCustomerDep
from app.presentation.reviews.schemas import (
    CreateReviewRequest,
    ProductReviewsResponse,
    ReviewResponse,
)

router = APIRouter(tags=["reviews"])

_view = require_permission(Permission.ORDERS_VIEW)
_manage = require_permission(Permission.ORDERS_MANAGE)


@router.post("/reviews", status_code=201)
@limiter.limit("20/hour")
async def create_review(
    request: Request,
    body: CreateReviewRequest,
    customer: CurrentCustomerDep,
    use_case: CreateReviewDep,
) -> ReviewResponse:
    review = await use_case.execute(body.to_command(customer.id))
    return ReviewResponse.from_entity(review)


@router.get("/storefront/{slug}/products/{product_id}/reviews")
@limiter.limit("300/minute")
async def list_storefront_product_reviews(
    request: Request, slug: str, product_id: int, use_case: ListProductReviewsDep
) -> ProductReviewsResponse:
    result = await use_case.execute(ListProductReviewsCommand(slug=slug, product_id=product_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return ProductReviewsResponse.from_result(result)


@router.get("/reviews/product/{product_id}", dependencies=[_view])
async def list_reviews_for_owner(
    product_id: int, actor: ActorDep, use_case: ListReviewsForOwnerDep
) -> list[ReviewResponse]:
    reviews = await use_case.execute(actor, ListReviewsForOwnerCommand(product_id=product_id))
    return [ReviewResponse.from_entity(r, include_hidden_flag=True) for r in reviews]


@router.post("/reviews/{review_id}/hide", dependencies=[_manage])
async def hide_review(
    review_id: int, actor: ActorDep, use_case: SetReviewHiddenDep
) -> ReviewResponse:
    review = await use_case.execute(actor, SetReviewHiddenCommand(review_id=review_id, is_hidden=True))
    return ReviewResponse.from_entity(review, include_hidden_flag=True)


@router.post("/reviews/{review_id}/unhide", dependencies=[_manage])
async def unhide_review(
    review_id: int, actor: ActorDep, use_case: SetReviewHiddenDep
) -> ReviewResponse:
    review = await use_case.execute(
        actor, SetReviewHiddenCommand(review_id=review_id, is_hidden=False)
    )
    return ReviewResponse.from_entity(review, include_hidden_flag=True)
