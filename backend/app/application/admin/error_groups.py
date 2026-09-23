"""Ошибки сервера для админки: запись, группировка, детали, «решено» (A5).

Хранилище — таблица error_log, не Redis: счётчики за 7 дней и вкладка
«Решённые» должны переживать перезапуск Redis. Redis остаётся буфером для
мгновенных алертов (см. observability/admin_alerts.py).

Чистка — при записи, а не отдельной задачей по расписанию: в проекте нет
планировщика, а заводить cron-контейнер ради одной операции избыточно.
Раз в _PURGE_EVERY записей удаляем всё старше _RETENTION_DAYS.
"""

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update

from app.infrastructure.db.models.errors import STACK_MAX_CHARS, ErrorLogModel

RETENTION_DAYS = 30
# «примерно раз в сто записей»: точный счётчик потребовал бы своего состояния,
# а для чистки достаточно вероятностного запуска
_PURGE_CHANCE = 0.01


@dataclass(frozen=True)
class ErrorGroup:
    signature: str
    type: str
    path: str
    method: str
    count_24h: int
    count_7d: int
    first_at: str
    last_at: str
    sample_id: int
    resolved: bool


@dataclass(frozen=True)
class ErrorEntry:
    id: int
    created_at: str
    method: str
    path: str
    error_type: str
    message: str
    status_code: int | None
    tenant_id: int | None
    stack: str
    resolved_at: str | None


def make_signature(error_type: str, method: str, path: str) -> str:
    """Одинаковые ошибки на одном маршруте — одна группа.

    Числовые сегменты пути схлопываются: /api/products/17 и /api/products/42 —
    это один и тот же случай, а не две разные ошибки.
    """
    normalized = "/".join(
        "{id}" if segment.isdigit() else segment for segment in path.split("/")
    )
    raw = f"{error_type}|{method}|{normalized}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def record_error(
    session_factory,
    *,
    error_type: str,
    method: str,
    path: str,
    message: str,
    stack: str = "",
    status_code: int | None = None,
    tenant_id: int | None = None,
) -> None:
    """Запись ошибки. Сама себя не роняет: потерянная строка лога не повод
    превращать одну ошибку в две."""
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        session.add(
            ErrorLogModel(
                signature=make_signature(error_type, method, path),
                error_type=error_type[:100],
                method=method[:10],
                path=path[:500],
                status_code=status_code,
                message=message[:500],
                stack=stack[:STACK_MAX_CHARS],
                tenant_id=tenant_id,
                created_at=now,
            )
        )
        if random.random() < _PURGE_CHANCE:
            await session.execute(
                delete(ErrorLogModel).where(
                    ErrorLogModel.created_at < now - timedelta(days=RETENTION_DAYS)
                )
            )
        await session.commit()


async def list_error_groups(
    session_factory,
    period_days: int = 1,
    only_unresolved: bool = True,
    error_type: str | None = None,
    path: str | None = None,
) -> list[ErrorGroup]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=period_days)
    d1 = now - timedelta(days=1)
    d7 = now - timedelta(days=7)

    async with session_factory() as session:
        stmt = (
            select(
                ErrorLogModel.signature,
                func.max(ErrorLogModel.error_type),
                func.max(ErrorLogModel.path),
                func.max(ErrorLogModel.method),
                func.count(ErrorLogModel.id).filter(ErrorLogModel.created_at >= d1),
                func.count(ErrorLogModel.id).filter(ErrorLogModel.created_at >= d7),
                func.min(ErrorLogModel.created_at),
                func.max(ErrorLogModel.created_at),
                func.max(ErrorLogModel.id),
                func.count(ErrorLogModel.resolved_at),
            )
            .where(ErrorLogModel.created_at >= since)
            .group_by(ErrorLogModel.signature)
            .order_by(func.count(ErrorLogModel.id).filter(ErrorLogModel.created_at >= d1).desc())
        )
        if error_type:
            stmt = stmt.where(ErrorLogModel.error_type == error_type)
        if path:
            stmt = stmt.where(ErrorLogModel.path.ilike(f"%{path}%"))
        if only_unresolved:
            stmt = stmt.where(ErrorLogModel.resolved_at.is_(None))

        rows = (await session.execute(stmt)).all()

    return [
        ErrorGroup(
            signature=r[0],
            type=r[1],
            path=r[2],
            method=r[3],
            count_24h=r[4],
            count_7d=r[5],
            first_at=r[6].isoformat(),
            last_at=r[7].isoformat(),
            sample_id=r[8],
            resolved=r[9] > 0,
        )
        for r in rows
    ]


async def get_error_entry(session_factory, entry_id: int) -> ErrorEntry | None:
    async with session_factory() as session:
        model = (
            await session.execute(select(ErrorLogModel).where(ErrorLogModel.id == entry_id))
        ).scalar_one_or_none()
    if model is None:
        return None
    return ErrorEntry(
        id=model.id,
        created_at=model.created_at.isoformat(),
        method=model.method,
        path=model.path,
        error_type=model.error_type,
        message=model.message,
        status_code=model.status_code,
        tenant_id=model.tenant_id,
        stack=model.stack,
        resolved_at=model.resolved_at.isoformat() if model.resolved_at else None,
    )


async def list_group_entries(
    session_factory, signature: str, limit: int = 20
) -> list[ErrorEntry]:
    async with session_factory() as session:
        models = (
            (
                await session.execute(
                    select(ErrorLogModel)
                    .where(ErrorLogModel.signature == signature)
                    .order_by(ErrorLogModel.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    return [
        ErrorEntry(
            id=m.id,
            created_at=m.created_at.isoformat(),
            method=m.method,
            path=m.path,
            error_type=m.error_type,
            message=m.message,
            status_code=m.status_code,
            tenant_id=m.tenant_id,
            stack=m.stack,
            resolved_at=m.resolved_at.isoformat() if m.resolved_at else None,
        )
        for m in models
    ]


async def resolve_group(session_factory, signature: str, resolved: bool = True) -> int:
    """Помечает группу решённой. Записи не удаляются — уходят во вкладку
    «Решённые», чтобы вернувшаяся ошибка была видна как рецидив."""
    async with session_factory() as session:
        result = await session.execute(
            update(ErrorLogModel)
            .where(ErrorLogModel.signature == signature)
            .values(resolved_at=datetime.now(timezone.utc) if resolved else None)
        )
        await session.commit()
        return result.rowcount or 0
