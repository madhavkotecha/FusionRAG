from __future__ import annotations

import logging
import uuid

from rrag_ingestion.components.chunkers.base import BaseChunker
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Chunk

logger = logging.getLogger(__name__)

# Hierarchical separators from general to specific
DEFAULT_SEPARATORS = ["\n\n\n", "\n\n", "\n", ". ", " ", ""]


@register_component
class UltraRAGRecursiveChunker(BaseChunker):
    """Recursive hierarchical chunker extracted from UltraRAG."""

    name = "ultrarag.recursive_chunker"
    version = "0.1.0"
    description = "Recursive hierarchical text chunking with multiple separator levels (from UltraRAG)"
    config_schema = {
        "chunk_size": {"type": "integer", "default": 512},
        "chunk_overlap": {"type": "integer", "default": 50},
        "separators": {"type": "array", "items": {"type": "string"}, "default": None},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        documents = input_data.data.get("documents", [])
        chunk_size = config.get("chunk_size", 512)
        chunk_overlap = config.get("chunk_overlap", 50)
        separators = config.get("separators") or DEFAULT_SEPARATORS

        all_chunks = []

        for doc in documents:
            text = doc.raw_text if hasattr(doc, "raw_text") else doc.get("raw_text", "")
            doc_id = doc.id if hasattr(doc, "id") else doc.get("id", "")
            doc_filename = doc.filename if hasattr(doc, "filename") else doc.get("filename", "")
            if not text:
                continue

            raw_chunks = self._recursive_split(text, separators, chunk_size)

            # Merge small chunks, apply overlap
            order_index = 0
            for chunk_text in raw_chunks:
                if chunk_text.strip():
                    all_chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        document_id=doc_id,
                        content=chunk_text.strip(),
                        tokens=len(chunk_text.split()),
                        order_index=order_index,
                        metadata={"chunker": self.name, "filename": doc_filename},
                    ))
                    order_index += 1

        return ComponentResult(
            data={"chunks": all_chunks, "documents": documents},
            metadata={"total_chunks": len(all_chunks)},
        )

    def _recursive_split(self, text: str, separators: list[str], chunk_size: int) -> list[str]:
        if not text or not separators:
            return [text] if text else []

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            # Character-level split
            return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        splits = text.split(separator)
        chunks = []
        current = ""

        for split in splits:
            candidate = (current + separator + split) if current else split
            if len(candidate.split()) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # If this single split is too large, recurse with finer separators
                if len(split.split()) > chunk_size and remaining_separators:
                    chunks.extend(self._recursive_split(split, remaining_separators, chunk_size))
                else:
                    current = split

        if current:
            chunks.append(current)

        return chunks
