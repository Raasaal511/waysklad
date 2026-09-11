from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.infrastructure.config import settings


class BcryptPasswordHasher:
    """Реализация IPasswordHasher."""

    def hash(self, password: str) -> str:
        return hash_password(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, tenant_id: int, role: str, token_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "tv": token_version,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def create_admin_access_token() -> str:
    """Отдельный scope claim ("admin") — токен обычного пользователя (create_access_token)
    и admin-токен подписаны одним secret_key, но не взаимозаменяемы: decode_admin_access_token
    проверяет scope, обычный decode_access_token его не содержит."""
    payload = {
        "scope": "admin",
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.admin_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_admin_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("scope") != "admin":
        raise jwt.InvalidTokenError("Не admin-токен")
    return payload
