from slugify import slugify


def generate_slug(text: str, max_length: int = 60) -> str:
    """Черновой slug для публичного URL: транслитерация + дефисы. «Айна» -> aina."""
    return slugify(text, max_length=max_length) or "shop"
