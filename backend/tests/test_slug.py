from app.domain.common.slug import generate_slug


def test_transliterates_cyrillic_shop_names():
    assert generate_slug("Магазин Беркат") == "magazin-berkat"
    assert generate_slug("СтройДом") == "stroidom"


def test_produces_lowercase_hyphenated_ascii():
    slug = generate_slug("Магазин «Айна» — платья и абайи!")
    assert slug.islower()
    assert " " not in slug
    assert all(c.isalnum() or c == "-" for c in slug)


def test_falls_back_to_shop_for_untransliterable_input():
    assert generate_slug("!!!") == "shop"
