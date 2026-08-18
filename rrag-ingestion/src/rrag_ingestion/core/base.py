from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ComponentType(str, Enum):
    PARSER = "parser"
    CHUNKER = "chunker"
    EXTRACTOR = "extractor"
    EMBEDDER = "embedder"
    INDEXER = "indexer"
    GRAPH_BUILDER = "graph_builder"
    STORAGE = "storage"
    RETRIEVER = "retriever"
    RERANKER = "reranker"
    GENERATOR = "generator"
    PLANNER = "planner"
    AGENT = "agent"


@dataclass
class ComponentResult:
    """Standard output from any component in the pipeline."""
    data: Any = None
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def is_ok(self) -> bool:
        return len(self.errors) == 0


class BaseComponent(ABC):
    """Base class for all pipeline components.

    Every component must implement invoke() and validate_config().
    Components are identified by a unique name (e.g. 'lightrag.token_chunker')
    and a type (e.g. ComponentType.CHUNKER).
    """

    name: str = ""
    component_type: ComponentType = ComponentType.PARSER
    version: str = "0.1.0"
    description: str = ""
    config_schema: dict = {}
    _progress_fn: Callable[[str, int, int], None] | None = None

    def report_progress(self, message: str, items_done: int = 0, items_total: int = 0) -> None:
        """Report sub-step progress during execution. Safe to call even if no callback is set."""
        if self._progress_fn:
            self._progress_fn(message, items_done, items_total)

    @abstractmethod
    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        """Process input data and return result.

        Args:
            input_data: Output from the previous pipeline step.
            config: Step-specific configuration overrides.

        Returns:
            ComponentResult with processed data.
        """
        ...

    def validate_config(self, config: dict) -> list[str]:
        """Validate component configuration. Returns list of error messages."""
        return []

    async def invoke_with_metrics(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        """Invoke with timing and error handling."""
        start = time.monotonic()
        try:
            result = await self.invoke(input_data, config)
            elapsed = time.monotonic() - start
            result.metadata["_duration_ms"] = round(elapsed * 1000, 2)
            result.metadata["_component"] = self.name
            return result
        except Exception as e:
            elapsed = time.monotonic() - start
            return ComponentResult(
                data=input_data.data,
                metadata={"_duration_ms": round(elapsed * 1000, 2), "_component": self.name},
                errors=[f"{self.name}: {type(e).__name__}: {e}"],
            )

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "type": self.component_type.value,
            "version": self.version,
            "description": self.description,
            "config_schema": self.config_schema,
        }


# Decorator for component registration
_COMPONENT_CLASSES: list[type[BaseComponent]] = []


def register_component(cls: type[BaseComponent]) -> type[BaseComponent]:
    """Decorator to register a component class for auto-discovery."""
    _COMPONENT_CLASSES.append(cls)
    return cls


def get_registered_components() -> list[type[BaseComponent]]:
    return list(_COMPONENT_CLASSES)
