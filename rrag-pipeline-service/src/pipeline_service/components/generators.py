from typing import Any

from .base import BaseComponent


class LLMGenerator(BaseComponent):
    """Stub: generates answers using a large language model."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        model = config.get("model", "gpt-4o")
        return {
            "response": (
                f"Mock LLM response from {model}. "
                "This is a placeholder answer based on the provided context."
            )
        }
