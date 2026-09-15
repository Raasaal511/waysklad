from typing import Protocol


class ICache(Protocol):
    """Кеширование произвольных значений по строковому ключу с TTL.

    Реализация не гарантирует сохранность значения — это именно кеш
    (cache-aside), а не хранилище: get() может вернуть None даже
    сразу после set() (Redis недоступен, память процесса перезапущена).
    Вызывающий код обязан уметь пересчитать значение при промахе.
    """

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None: ...

    async def delete_prefix(self, prefix: str) -> None:
        """Удаляет все ключи, начинающиеся с prefix — инвалидация по tenant_id
        при мутациях (см. SqlAlchemyUnitOfWork.commit), а не ожидание TTL."""
        ...
