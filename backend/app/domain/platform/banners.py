from dataclasses import dataclass
from datetime import date

from app.domain.common.exceptions import DomainError

PLACEMENTS: tuple[str, ...] = ("hero", "promo")
THEMES: tuple[str, ...] = ("light", "accent", "dark")


@dataclass
class PlatformBanner:
    """Баннер платформы (карусель hero или промо-плитки главной маркетплейса) —
    глобальный, без tenant_id, ведётся только админом (см. промпт M-B2 п.1)."""

    id: int | None
    placement: str  # 'hero' | 'promo'
    title: str
    subtitle: str = ""
    button_text: str = ""
    link: str = ""
    image: str = ""
    image_mobile: str = ""
    theme: str = "light"  # 'light' | 'accent' | 'dark' — фронт превращает в цвета темы
    sort_order: int = 0
    is_active: bool = True
    starts_at: date | None = None
    ends_at: date | None = None
    city: str | None = None  # None — показывать во всех городах

    def is_live(self, today: date, city: str | None) -> bool:
        """Активен по датам (включительно) и подходит запрошенному городу —
        баннер без city показывается всем, баннер с city — только совпадающему
        запросу (city=None в запросе показывает баннеры для всех городов сразу,
        см. промпт M-B2 п.2: сужение по конкретному городу выбирает вызывающий)."""
        if not self.is_active:
            return False
        if self.starts_at is not None and today < self.starts_at:
            return False
        if self.ends_at is not None and today > self.ends_at:
            return False
        if self.city is not None and city is not None and self.city != city:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "placement": self.placement,
            "title": self.title,
            "subtitle": self.subtitle,
            "button_text": self.button_text,
            "link": self.link,
            "image": self.image,
            "image_mobile": self.image_mobile,
            "theme": self.theme,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "city": self.city,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlatformBanner":
        return cls(
            id=d["id"],
            placement=d["placement"],
            title=d["title"],
            subtitle=d.get("subtitle", ""),
            button_text=d.get("button_text", ""),
            link=d.get("link", ""),
            image=d.get("image", ""),
            image_mobile=d.get("image_mobile", ""),
            theme=d.get("theme", "light"),
            sort_order=d.get("sort_order", 0),
            is_active=d.get("is_active", True),
            starts_at=date.fromisoformat(d["starts_at"]) if d.get("starts_at") else None,
            ends_at=date.fromisoformat(d["ends_at"]) if d.get("ends_at") else None,
            city=d.get("city"),
        )


def validate_banner_link(link: str) -> None:
    """Только относительный путь (/…) или https:// — блокирует javascript:,
    data:, http:// (не шифрованный) и прочие схемы (см. промпт M-B2 п.1)."""
    if not link:
        return
    if link.startswith("/"):
        return
    if link.startswith("https://"):
        return
    raise DomainError("Ссылка баннера должна быть относительным путём или https://")


def validate_placement(placement: str) -> None:
    if placement not in PLACEMENTS:
        raise DomainError(f"Неизвестное расположение баннера: «{placement}»")


def validate_theme(theme: str) -> None:
    if theme not in THEMES:
        raise DomainError(f"Неизвестная тема баннера: «{theme}»")
