from typing import Protocol


class IFileStorage(Protocol):
    """Реализация — infrastructure/files.py (локальный диск)."""

    def save(self, filename: str, content: bytes) -> str: ...
    def delete(self, photo_url: str) -> None: ...
