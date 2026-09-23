from datetime import datetime

from pydantic import BaseModel

from app.domain.feedback.entities import Feedback


class FeedbackResponse(BaseModel):
    id: int
    topic: str
    text: str
    photos: list[str]
    created_at: datetime | None

    @classmethod
    def from_entity(cls, feedback: Feedback) -> "FeedbackResponse":
        return cls(
            id=feedback.id,
            topic=feedback.topic.value,
            text=feedback.text,
            photos=feedback.photos,
            created_at=feedback.created_at,
        )
