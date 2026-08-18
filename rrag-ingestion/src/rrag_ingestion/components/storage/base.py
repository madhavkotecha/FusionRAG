from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import StorageConfig


@dataclass
class StorageInput:
    """Typed input for storage components."""
    data: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StorageOutput:
    """Typed output from storage components."""
    stored: bool = False
    count: int = 0
    reference: str = ""


class BaseStorage(BaseComponent):
    """Base class for data persistence backends.

    Supports vector, graph, key-value, and document storage.
    """

    component_type = ComponentType.STORAGE
    ConfigModel = StorageConfig

    input_ports = [
        {"name": "data", "type": "any", "description": "Data to store"},
    ]
    output_ports = [
        {"name": "stored", "type": "any", "description": "Storage confirmation"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            StorageConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
