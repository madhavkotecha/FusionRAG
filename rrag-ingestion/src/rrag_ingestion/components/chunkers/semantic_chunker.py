from __future__ import annotations

import logging
import uuid

from rrag_ingestion.components.chunkers.base import BaseChunker
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Chunk

logger = logging.getLogger(__name__)


@register_component
class KAGSemanticChunker(BaseChunker):
    """Semantic coherence-based chunker inspired by KAG's semantic splitter."""

    name = "kag.semantic_chunker"
    version = "0.1.0"
    description = "Splits text at semantic boundaries (headings, topic shifts) inspired by KAG"
    config_schema = {
        "max_chunk_size": {"type": "integer", "default": 500, "description": "Max words per chunk"},
        "heading_patterns": {
            "type": "array",
            "default": ["^#{1,6}\\s", "^\\d+\\.\\s", "^[A-Z][^.!?]*:$"],
            "description": "Regex patterns that indicate section headings",
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        documents = input_data.data.get("documents", [])
        max_size = config.get("max_chunk_size", 500)
        heading_patterns = config.get("heading_patterns", ["^#{1,6}\\s", "^\\d+\\.\\s"])

        import re
        patterns = [re.compile(p, re.MULTILINE) for p in heading_patterns]

        all_chunks = []

        for doc in documents:
            text = doc.raw_text if hasattr(doc, "raw_text") else doc.get("raw_text", "")
            doc_id = doc.id if hasattr(doc, "id") else doc.get("id", "")
            doc_filename = doc.filename if hasattr(doc, "filename") else doc.get("filename", "")
            if not text:
                continue

            # Find all heading positions
            break_positions = {0}
            for pattern in patterns:
                for match in pattern.finditer(text):
                    break_positions.add(match.start())
            break_positions = sorted(break_positions)

            # Create sections between headings
            sections = []
            for i, pos in enumerate(break_positions):
                end = break_positions[i + 1] if i + 1 < len(break_positions) else len(text)
                section = text[pos:end].strip()
                if section:
                    sections.append(section)

            if not sections:
                sections = [text]

            # Merge small sections, split large ones
            order_index = 0
            current = ""
            for section in sections:
                if len((current + " " + section).split()) <= max_size:
                    current = (current + "\n\n" + section).strip()
                else:
                    if current:
                        all_chunks.append(Chunk(
                            id=str(uuid.uuid4()),
                            document_id=doc_id,
                            content=current,
                            tokens=len(current.split()),
                            order_index=order_index,
                            metadata={"chunker": self.name, "filename": doc_filename},
                        ))
                        order_index += 1
                    current = section

            if current:
                all_chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    content=current,
                    tokens=len(current.split()),
                    order_index=order_index,
                    metadata={"chunker": self.name, "filename": doc_filename},
                ))

        return ComponentResult(
            data={"chunks": all_chunks, "documents": documents},
            metadata={"total_chunks": len(all_chunks)},
        )
