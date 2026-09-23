from dataclasses import dataclass


@dataclass
class PlatformCategory:
    """Справочник категорий платформы — общий для всех магазинов, без tenant_id.
    Категория магазина (app.domain.catalog.entities.Category) опционально
    ссылается на неё через platform_category_id, чтобы товары разных
    магазинов можно было сгруппировать по одному общему разделу маркетплейса."""

    id: int | None
    name: str
    slug: str
    image: str = ""
    sort_order: int = 0
    is_active: bool = True
    parent_id: int | None = None  # один уровень вложенности — родитель обязан быть без своего parent_id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "image": self.image,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlatformCategory":
        return cls(
            id=d["id"],
            name=d["name"],
            slug=d["slug"],
            image=d.get("image", ""),
            sort_order=d.get("sort_order", 0),
            is_active=d.get("is_active", True),
            parent_id=d.get("parent_id"),
        )
