from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base

# стек обрезается при записи: полный трейсбек бывает на десятки килобайт,
# а для диагностики хватает верхних кадров
STACK_MAX_CHARS = 8000


class ErrorLogModel(Base):
    """Необработанная ошибка сервера — для админ-панели платформы.

    Не TenantMixin: ошибка может случиться и вне tenant-контекста (публичные
    страницы, вебхуки), а tenant_id здесь — справочное поле, не скоуп доступа.

    Персональных данных не храним намеренно: ни тела запроса, ни заголовков,
    ни телефонов, ни параметров — только время, путь, метод, тип, статус,
    сообщение, стек, tenant_id и сигнатуру. Записи старше 30 дней удаляются
    (см. SqlAlchemyErrorLogRepository.purge_old).
    """

    __tablename__ = "error_log"
    __table_args__ = (
        # группировка по сигнатуре за период — основной запрос админки
        Index("ix_error_log_signature_created", "signature", "created_at"),
        Index("ix_error_log_created", "created_at"),
        Index("ix_error_log_resolved", "resolved_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # sha256 от типа, метода и пути — одинаковые ошибки схлопываются в группу
    signature: Mapped[str] = mapped_column(String(64))
    error_type: Mapped[str] = mapped_column(String(100))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    status_code: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(500), default="")
    stack: Mapped[str] = mapped_column(Text, default="")
    tenant_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # проставляется, когда админ нажал «Решено» на группе; записи не удаляются,
    # а уходят во вкладку «Решённые»
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
