from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app.application.reviews.check_review_eligibility import CheckReviewEligibilityCommand
from app.application.reviews.list_product_reviews import ListProductReviewsCommand
from app.application.reviews.list_reviews_for_owner import ListReviewsForOwnerCommand
from app.application.reviews.set_review_hidden import SetReviewHiddenCommand
from app.application.reviews.upload_review_photo import UploadReviewPhotoCommand
from app.application.reviews.vote_review import VoteReviewCommand
from app.domain.identity.permissions import Permission
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import (
    ActorDep,
    CheckReviewEligibilityDep,
    CreateReviewDep,
    ListAllReviewsForOwnerDep,
    ListProductReviewsDep,
    ListReviewsForOwnerDep,
    SetReviewHiddenDep,
    UploadReviewPhotoDep,
    VoteReviewDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.deps.customer_auth import CurrentCustomerDep, CurrentCustomerOptionalDep
from app.presentation.reviews.schemas import (
    AllReviewsForOwnerParams,
    AllReviewsForOwnerResponse,
    CreateReviewRequest,
    OwnerProductReviewsResponse,
    ProductReviewsResponse,
    ReviewEligibilityResponse,
    ReviewResponse,
    ReviewTagResponse,
    StorefrontProductReviewsParams,
    UploadReviewPhotoResponse,
    VoteReviewRequest,
    VoteReviewResponse,
    all_review_tags,
)

router = APIRouter(tags=["reviews"])

_view = require_permission(Permission.ORDERS_VIEW)
_manage = require_permission(Permission.ORDERS_MANAGE)


@router.get("/reviews/tags")
async def list_review_tags() -> list[ReviewTagResponse]:
    return all_review_tags()


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


@router.post("/reviews/photos", status_code=201)
@limiter.limit("30/hour")
async def upload_review_photo(
    request: Request,
    customer: CurrentCustomerDep,
    use_case: UploadReviewPhotoDep,
    file: UploadFile,
) -> UploadReviewPhotoResponse:
    url = await use_case.execute(
        UploadReviewPhotoCommand(
            customer_id=customer.id, filename=file.filename or "photo.jpg", content=await file.read()
        )
    )
    return UploadReviewPhotoResponse(url=url)


@router.put("/reviews/{review_id}/vote")
@limiter.limit("60/hour")
async def vote_review(
    request: Request, review_id: int, body: VoteReviewRequest, customer: CurrentCustomerDep, use_case: VoteReviewDep
) -> VoteReviewResponse:
    result = await use_case.execute(
        VoteReviewCommand(customer_id=customer.id, review_id=review_id, value=body.value)
    )
    return VoteReviewResponse.from_result(result)


@router.get("/storefront/{slug}/products/{product_id}/reviews")
@limiter.limit("300/minute")
async def list_storefront_product_reviews(
    request: Request,
    slug: str,
    product_id: int,
    params: Annotated[StorefrontProductReviewsParams, Depends()],
    customer: CurrentCustomerOptionalDep,
    use_case: ListProductReviewsDep,
) -> ProductReviewsResponse:
    result = await use_case.execute(
        ListProductReviewsCommand(
            slug=slug,
            product_id=product_id,
            filters=params.to_filter(),
            customer_id=customer.id if customer is not None else None,
        )
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return ProductReviewsResponse.from_result(result)


@router.get("/storefront/{slug}/products/{product_id}/reviews/eligibility")
async def get_review_eligibility(
    slug: str, product_id: int, customer: CurrentCustomerDep, use_case: CheckReviewEligibilityDep
) -> ReviewEligibilityResponse:
    result = await use_case.execute(
        CheckReviewEligibilityCommand(slug=slug, product_id=product_id, customer_id=customer.id)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return ReviewEligibilityResponse.from_result(result)


@router.get("/reviews", dependencies=[_view])
async def list_all_reviews_for_owner(
    params: Annotated[AllReviewsForOwnerParams, Depends()],
    actor: ActorDep,
    use_case: ListAllReviewsForOwnerDep,
) -> AllReviewsForOwnerResponse:
    result = await use_case.execute(actor, params.to_command())
    return AllReviewsForOwnerResponse.from_result(result)


@router.get("/reviews/product/{product_id}", dependencies=[_view])
async def list_reviews_for_owner(
    product_id: int, actor: ActorDep, use_case: ListReviewsForOwnerDep
) -> OwnerProductReviewsResponse:
    result = await use_case.execute(actor, ListReviewsForOwnerCommand(product_id=product_id))
    return OwnerProductReviewsResponse.from_result(result)


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
