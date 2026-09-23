"""Чтение метаданных, которые кладут внешние скрипты.

Backend намеренно не ходит ни в /etc/letsencrypt, ни в каталоги бэкапов:
у процесса приложения нет причин иметь туда доступ. Вместо этого сертификатный
хук и скрипт бэкапа сами пишут маленькие JSON-файлы в settings.status_dir, а
здесь они только читаются.

Файла нет или он битый — возвращаем None. Задача прямо требует: чего получить
нельзя, то null, а не выдуманный ноль.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.infrastructure.config import settings
from app.infrastructure.observability.logging import get_logger

_logger = get_logger("app.status_files")

TLS_FILE = "tls.json"
BACKUP_FILE = "backup.json"


@dataclass(frozen=True)
class TlsStatus:
    domain: str
    expires_at: str
    days_left: int


@dataclass(frozen=True)
class BackupStatus:
    last_at: str | None
    size_bytes: int | None
    # false, пока внешняя копия не настроена — честно, а не «наверное, есть»
    offsite_ok: bool


def _read_json(name: str) -> dict | None:
    path = Path(settings.status_dir) / name
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        # битый файл — не повод ронять админку, но знать о нём стоит
        _logger.warning("Не удалось прочитать %s", path, exc_info=True)
        return None
    return data if isinstance(data, dict) else None


def read_tls_status() -> TlsStatus | None:
    data = _read_json(TLS_FILE)
    if not data or not data.get("expires_at"):
        return None
    try:
        expires = datetime.fromisoformat(str(data["expires_at"]))
    except ValueError:
        _logger.warning("Некорректная дата в %s", TLS_FILE)
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    days_left = (expires - datetime.now(timezone.utc)).days
    return TlsStatus(
        domain=str(data.get("domain", "")),
        expires_at=expires.isoformat(),
        days_left=days_left,
    )


def read_backup_status() -> BackupStatus | None:
    data = _read_json(BACKUP_FILE)
    if not data:
        return None
    size = data.get("size_bytes")
    return BackupStatus(
        last_at=str(data["last_at"]) if data.get("last_at") else None,
        size_bytes=int(size) if isinstance(size, (int, float, str)) and str(size).isdigit() else None,
        offsite_ok=bool(data.get("offsite_ok", False)),
    )
