from __future__ import annotations

import logging
import re
import uuid

from rrag_ingestion.components.chunkers.base import BaseChunker
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Chunk

logger = logging.getLogger(__name__)

SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')


@register_component
class UltraRAGSentenceChunker(BaseChunker):
    """Sentence-based chunker extracted from UltraRAG."""

    name = "ultrarag.sentence_chunker"
    version = "0.1.0"
    description = "Sentence-based text chunking with min/max sentence grouping (from UltraRAG)"
    config_schema = {
        "min_sentences": {"type": "integer", "default": 3},
        "max_sentences": {"type": "integer", "default": 10},
        "overlap_sentences": {"type": "integer", "default": 1},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        documents = input_data.data.get("documents", [])
        min_sent = config.get("min_sentences", 3)
        max_sent = config.get("max_sentences", 10)
        overlap = config.get("overlap_sentences", 1)

        all_chunks = []

        for doc in documents:
            text = doc.raw_text if hasattr(doc, "raw_text") else doc.get("raw_text", "")
            doc_id = doc.id if hasattr(doc, "id") else doc.get("id", "")
            doc_filename = doc.filename if hasattr(doc, "filename") else doc.get("filename", "")
            if not text:
                continue

            sentences = SENTENCE_ENDINGS.split(text)
            sentences = [s.strip() for s in sentences if s.strip()]

            order_index = 0
            i = 0
            while i < len(sentences):
                end = min(i + max_sent, len(sentences))
                if end - i < min_sent and i > 0:
                    break  # Not enough sentences for a new chunk

                chunk_sentences = sentences[i:end]
                chunk_text = " ".join(chunk_sentences)

                all_chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    content=chunk_text,
                    tokens=len(chunk_text.split()),
                    order_index=order_index,
                    metadata={"chunker": self.name, "filename": doc_filename, "sentence_count": len(chunk_sentences)},
                ))
                order_index += 1
                i = end - overlap if overlap > 0 else end

        return ComponentResult(
            data={"chunks": all_chunks, "documents": documents},
            metadata={"total_chunks": len(all_chunks)},
        )
