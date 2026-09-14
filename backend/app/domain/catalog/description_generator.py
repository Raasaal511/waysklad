from typing import Protocol


class IDescriptionGenerator(Protocol):
    """Генерация текста описания товара для витрины (реализация —
    infrastructure/ai/anthropic_description_generator.py). Возвращает только
    предложенный текст, ничего не сохраняет."""

    async def generate(self, product_name: str, category_name: str) -> str: ...
