from anthropic import AsyncAnthropic

from app.domain.common.exceptions import DomainError
from app.infrastructure.config import settings

_SYSTEM_PROMPT = (
    "Ты пишешь короткое описание товара для карточки на витрине интернет-магазина. "
    "1-3 предложения, по-русски, без markdown-разметки, без эмодзи, без воды и "
    "преувеличений — только то, что реально помогает покупателю понять, что это за товар."
)


class AnthropicDescriptionGenerator:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise DomainError("Генерация описания через ИИ не настроена")
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(self, product_name: str, category_name: str) -> str:
        user_prompt = f"Товар: {product_name}"
        if category_name:
            user_prompt += f"\nКатегория: {category_name}"

        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=300,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
