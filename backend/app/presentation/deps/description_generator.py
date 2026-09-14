from typing import Annotated

from fastapi import Depends

from app.domain.catalog.description_generator import IDescriptionGenerator
from app.infrastructure.ai.anthropic_description_generator import (
    AnthropicDescriptionGenerator,
)


def get_description_generator() -> IDescriptionGenerator:
    return AnthropicDescriptionGenerator()


DescriptionGeneratorDep = Annotated[
    IDescriptionGenerator, Depends(get_description_generator)
]
