import uuid
from pathlib import Path

from app.domain.common.exceptions import DomainError

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ


class LocalFileStorage:
    """Реализация IFileStorage: сохраняет файл на диск, отдаётся через StaticFiles /uploads."""

    def __init__(self, upload_dir: Path = UPLOAD_DIR):
        self._upload_dir = upload_dir
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> str:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise DomainError(f"Недопустимый формат файла: {ext or 'без расширения'}")
        if len(content) > MAX_FILE_SIZE:
            raise DomainError("Файл слишком большой (максимум 5 МБ)")
        name = f"{uuid.uuid4().hex}{ext}"
        (self._upload_dir / name).write_bytes(content)
        return f"/uploads/{name}"
