import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps

from app.domain.common.exceptions import DomainError

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ — приходящий с телефона оригинал; хранится он уже пережатым

# Оригинал переупаковывается в WebP одним размером — полноразмерные фото с телефона
# (обычно несколько МБ, тысячи px) не нужны ни на диске, ни в трафике браузера.
FULL_SIZE = 1200


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

        try:
            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)  # честно повернуть фото с телефона
            image = image.convert("RGB")
        except Exception as exc:
            raise DomainError("Не удалось распознать изображение") from exc

        name = f"{uuid.uuid4().hex}.webp"
        self._save_resized(image, self._upload_dir / name, FULL_SIZE)
        return f"/uploads/{name}"

    def delete(self, photo_url: str) -> None:
        """Удаляет файл по URL, ранее возвращённому save(). Тихо игнорирует отсутствующий файл."""
        if not photo_url:
            return
        (self._upload_dir / Path(photo_url).name).unlink(missing_ok=True)

    @staticmethod
    def _save_resized(image: Image.Image, path: Path, max_side: int) -> None:
        resized = image.copy()
        resized.thumbnail((max_side, max_side), Image.LANCZOS)
        resized.save(path, "WEBP", quality=82, method=6)
