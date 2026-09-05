from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.infrastructure.db.models.telegram_bot import TelegramBotSessionModel


class PostgresStorage(BaseStorage):
    """FSM-хранилище aiogram на существующей Postgres-БД — без Redis, без
    отдельной инфраструктуры (принцип проекта — не тащить лишний сервис под
    одну задачу). Диалог покупателя переживает рестарт процесса бота."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def set_state(self, key: StorageKey, state: State | str | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        async with self._session_factory() as session:
            await self._upsert(session, key, state=value)
            await session.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._session_factory() as session:
            model = await self._get(session, key)
            return model.state if model else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        async with self._session_factory() as session:
            await self._upsert(session, key, data=dict(data))
            await session.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._session_factory() as session:
            model = await self._get(session, key)
            return dict(model.data) if model else {}

    async def close(self) -> None:
        pass  # session_factory общий для всего процесса — закрывать нечего

    async def _get(self, session, key: StorageKey) -> TelegramBotSessionModel | None:
        return (
            await session.execute(
                select(TelegramBotSessionModel).where(
                    TelegramBotSessionModel.bot_id == key.bot_id,
                    TelegramBotSessionModel.chat_id == key.chat_id,
                    TelegramBotSessionModel.user_id == key.user_id,
                )
            )
        ).scalar_one_or_none()

    async def _upsert(
        self, session, key: StorageKey, state: str | None | Any = ..., data: dict | None = None
    ) -> None:
        # ... как sentinel — set_state не должен затирать уже сохранённые data,
        # и наоборот; частичный upsert через ON CONFLICT DO UPDATE конкретных колонок
        values: dict[str, Any] = {"bot_id": key.bot_id, "chat_id": key.chat_id, "user_id": key.user_id}
        update: dict[str, Any] = {}
        if state is not ...:
            values["state"] = state
            update["state"] = state
        if data is not None:
            values["data"] = data
            update["data"] = data
        if not update:
            return
        stmt = pg_insert(TelegramBotSessionModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["bot_id", "chat_id", "user_id"], set_=update
        )
        await session.execute(stmt)
