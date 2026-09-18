from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.catalog.ports import IFileStorage
from app.domain.common.exceptions import DomainError
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_RATE_LIMIT_PER_HOUR = 30


@dataclass(frozen=True)
class UploadReviewPhotoCommand:
    customer_id: int
    filename: str
    content: bytes


class UploadReviewPhotoUseCase:
    """Покупатель загружает фото для будущего отзыва (может случиться до
    выбора товара/заявки — тот же порядок действий, что и в приложениях
    маркетплейсов: сначала фото, текст и оценка, потом «Отправить»). Своя
    таблица review_uploads (не привязана к tenant — покупатель ещё мог не
    определиться, к какому магазину/товару относится фото) фиксирует
    привязку url -> customer_id, чтобы CreateReviewUseCase мог проверить
    владение при создании самого отзыва (промпт B3 п.2).

    Rate limit 30/час — ПОВЕРХ уже применённого на роутере slowapi-лимита по
    IP: здесь лимит именно по customer_id, отдельная защита от одного
    авторизованного покупателя, заливающего фото через разные IP/устройства."""

    def __init__(self, session_factory, storage: IFileStorage):
        self._session_factory = session_factory
        self._storage = storage

    async def execute(self, cmd: UploadReviewPhotoCommand) -> str:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            since = datetime.now(UTC) - timedelta(hours=1)
            recent = await uow.review_uploads.count_recent(cmd.customer_id, since)
            if recent >= _RATE_LIMIT_PER_HOUR:
                raise DomainError("Слишком много загрузок фото, попробуйте позже")

            url = self._storage.save(cmd.filename, cmd.content)
            await uow.review_uploads.add(None, cmd.customer_id, url)
            await uow.commit()
            return url
