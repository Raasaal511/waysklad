from typing import Protocol


class IPasswordHasher(Protocol):
    """Реализация — infrastructure/security.py (bcrypt)."""

    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...
