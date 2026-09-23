"""Словарь синонимов для автосопоставления категорий магазина с платформенными
(scripts/map_platform_categories.py). Ключ — платформенный slug (см. SEED_PLATFORM_CATEGORIES
ниже и сид-миграцию platform_categories, которая использует тот же список),
значение — нормализованные названия (lower, trim, ё->е), которые считаются тем
же самым. Название самой платформенной категории уже входит в сопоставление
неявно (normalize(name) == normalize(platform_name))."""

# (slug, name, sort_order) — общий источник и для сид-миграции, и для тестовой
# БД (которая создаётся из моделей напрямую, Base.metadata.create_all, а не
# через Alembic — см. tests/conftest.py db_session_factory)
SEED_PLATFORM_CATEGORIES: tuple[tuple[str, str, int], ...] = (
    ("electronics", "Электроника", 10),
    ("clothing", "Одежда", 20),
    ("shoes", "Обувь", 30),
    ("tools", "Инструменты", 40),
    ("auto", "Автотовары", 50),
    ("accessories", "Аксессуары", 60),
    ("food", "Продукты", 70),
    ("home", "Для дома", 80),
    ("beauty", "Красота", 90),
    ("kids", "Детские товары", 100),
    ("construction", "Строительство", 110),
    ("other", "Прочее", 120),
)

CATEGORY_SYNONYMS: dict[str, frozenset[str]] = {
    "electronics": frozenset({
        "электроника", "техника", "бытовая техника", "гаджеты", "телефоны",
        "смартфоны", "компьютеры", "ноутбуки",
    }),
    "clothing": frozenset({
        "одежда", "одежда и обувь", "мужская одежда", "женская одежда", "текстиль",
    }),
    "shoes": frozenset({
        "обувь", "кроссовки", "туфли", "ботинки", "сапоги",
    }),
    "tools": frozenset({
        "инструменты", "инструмент", "стройинструмент", "электроинструменты",
    }),
    "auto": frozenset({
        "автотовары", "авто", "автозапчасти", "автотовар", "запчасти",
    }),
    "accessories": frozenset({
        "аксессуары", "сумки", "часы", "украшения", "бижутерия",
    }),
    "food": frozenset({
        "продукты", "продукты питания", "еда", "напитки",
    }),
    "home": frozenset({
        "для дома", "дом", "товары для дома", "посуда", "мебель", "быт",
    }),
    "beauty": frozenset({
        "красота", "косметика", "парфюмерия", "уход", "здоровье",
    }),
    "kids": frozenset({
        "детские товары", "детские", "товары для детей", "игрушки",
    }),
    "construction": frozenset({
        "строительство", "стройматериалы", "ремонт", "стройка",
    }),
}


def normalize_category_name(name: str) -> str:
    return name.strip().lower().replace("ё", "е")


def match_platform_slug(category_name: str) -> str | None:
    """Платформенный slug для названия категории магазина, либо None —
    несопоставленные категории остаются platform_category_id=null."""
    normalized = normalize_category_name(category_name)
    for slug, synonyms in CATEGORY_SYNONYMS.items():
        if normalized in synonyms:
            return slug
    return None
