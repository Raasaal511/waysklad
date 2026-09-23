from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile

from app.application.feedback.submit_feedback import (
    FeedbackPhoto,
    SubmitFeedbackCommand,
    notify_admin_about_feedback,
)
from app.domain.common.exceptions import DomainError
from app.domain.feedback.entities import MAX_FEEDBACK_PHOTOS
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import ActorDep, SubmitFeedbackDep
from app.presentation.deps.notifier import NotifierDep
from app.presentation.feedback.schemas import FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=201)
@limiter.limit("20/hour")
async def submit_feedback(
    request: Request,
    background: BackgroundTasks,
    actor: ActorDep,
    use_case: SubmitFeedbackDep,
    notifier: NotifierDep,
    topic: Annotated[str, Form()],
    text: Annotated[str, Form()] = "",
    page: Annotated[str, Form()] = "",
    app_version: Annotated[str, Form()] = "",
    photos: Annotated[list[UploadFile] | None, File()] = None,
) -> FeedbackResponse:
    """Обращение в поддержку платформы из кабинета: multipart, фото — до 3 файлов.

    Одним запросом, а не «сначала фото, потом обращение»: у брошенной формы
    не остаётся осиротевших файлов на диске.
    """
    files = photos or []
    # до чтения файлов в память — лишние 5-мегабайтные фото незачем читать
    if len(files) > MAX_FEEDBACK_PHOTOS:
        raise DomainError(f"Можно прикрепить не больше {MAX_FEEDBACK_PHOTOS} фото")
    submitted = await use_case.execute(
        actor,
        SubmitFeedbackCommand(
            topic=topic,
            text=text,
            photos=[FeedbackPhoto(f.filename or "photo.jpg", await f.read()) for f in files],
            page=page,
            user_agent=request.headers.get("user-agent", ""),
            app_version=app_version,
        ),
    )
    background.add_task(notify_admin_about_feedback, notifier, submitted)
    return FeedbackResponse.from_entity(submitted.feedback)
