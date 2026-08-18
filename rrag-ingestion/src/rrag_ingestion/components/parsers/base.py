from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.core.base import BaseComponent, ComponentType
from rrag_ingestion.core.schemas import ParserConfig


@dataclass
class ParserInput:
    """Typed input for parsers."""
    file_path: str | None = None
    file_bytes: bytes | None = None
    url: str | None = None
    content_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParserOutput:
    """Typed output from parsers."""
    documents: list[dict[str, Any]] = field(default_factory=list)


class BaseParser(BaseComponent):
    """Base class for document parsers and data source loaders.

    Input:  Raw file bytes, file path, or URL
    Output: list[Document] with raw_text and metadata
    """

    component_type = ComponentType.PARSER
    ConfigModel = ParserConfig

    input_ports = [
        {"name": "file_path", "type": "string", "description": "Path to file or directory"},
    ]
    output_ports = [
        {"name": "documents", "type": "document_list", "description": "Parsed documents"},
    ]

    def validate_config(self, config: dict) -> list[str]:
        """Validate config using Pydantic model."""
        try:
            ParserConfig(**config)
            return []
        except Exception as e:
            return [str(e)]
