from typing import Protocol


class IMetricsHistory(Protocol):
    """История точек CPU/память за последний час — не гарантирует сохранность
    (реализация — Redis, см. app.infrastructure.observability.metrics_history):
    диагностика, не аудит, промах Redis просто даёт пустую/неполную историю."""

    async def record(self, cpu_percent: float, memory_percent: float) -> None:
        """Добавляет точку, только если прошло достаточно времени с прошлой
        записи (throttling — реализация решает интервал), не на каждый вызов."""
        ...

    async def list_recent(self) -> list[dict]: ...
