from abc import ABC, abstractmethod
from typing import Any


class BaseComponent(ABC):
    """Abstract base class for all pipeline components."""

    @abstractmethod
    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        ...
