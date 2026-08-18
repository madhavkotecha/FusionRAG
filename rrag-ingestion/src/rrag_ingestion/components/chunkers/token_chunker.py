from __future__ import annotations

import logging
import uuid
from typing import Any

from rrag_ingestion.components.chunkers.base import BaseChunker
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Chunk

logger = logging.getLogger(__name__)


def _get_tokenizer():
    """Get tiktoken tokenizer, with fallback to simple whitespace splitting."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4o-mini")
        return enc.encode, enc.decode
    except ImportError:
        # Fallback: simple whitespace tokenizer
        def encode(text: str) -> list[int]:
            return list(range(len(text.split())))
        def decode(tokens: list[int]) -> str:
            return ""  # Not used in chunking
        return encode, decode


@register_component
class LightRAGTokenChunker(BaseChunker):
    """Token-based chunker extracted from LightRAG's chunking_by_token_size."""

    name = "lightrag.token_chunker"
    version = "0.1.0"
    description = "Token-based text chunking with configurable size and overlap (from LightRAG)"
    config_schema = {
        "chunk_token_size": {"type": "integer", "default": 1200, "description": "Max tokens per chunk"},
        "chunk_overlap_token_size": {"type": "integer", "default": 100, "description": "Overlap tokens between chunks"},
        "split_by_character": {"type": "string", "default": None, "description": "Optional character to split by first"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        documents = input_data.data.get("documents", [])
        chunk_size = config.get("chunk_token_size", 1200)
        overlap = config.get("chunk_overlap_token_size", 100)
        split_char = config.get("split_by_character")

        encode, _ = _get_tokenizer()
        all_chunks = []
        errors = []

        for doc in documents:
            text = doc.raw_text if hasattr(doc, "raw_text") else doc.get("raw_text", "")
            doc_id = doc.id if hasattr(doc, "id") else doc.get("id", str(uuid.uuid4()))
            doc_filename = doc.filename if hasattr(doc, "filename") else doc.get("filename", "")
            if not text:
                continue

            try:
                chunks = self._chunk_text(text, doc_id, chunk_size, overlap, split_char, encode, doc_filename)
                all_chunks.extend(chunks)
            except Exception as e:
                errors.append(f"Chunking failed for doc {doc_id}: {e}")

        return ComponentResult(
            data={"chunks": all_chunks, "documents": documents},
            metadata={"total_chunks": len(all_chunks)},
            errors=errors,
        )

    def _chunk_text(
        self,
        text: str,
        doc_id: str,
        chunk_size: int,
        overlap: int,
        split_char: str | None,
        encode,
        doc_filename: str = "",
    ) -> list[Chunk]:
        # Tokenize the full text and split by token windows
        tokens = encode(text)
        if not tokens:
            return []

        # If text fits in a single chunk, return it directly
        if len(tokens) <= chunk_size:
            return [Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                content=text.strip(),
                tokens=len(tokens),
                order_index=0,
                metadata={"chunker": self.name, "filename": doc_filename},
            )]

        # Split into overlapping token windows
        # Use sentence boundaries within each window for cleaner splits
        sentences = self._split_into_sentences(text)
        sentence_tokens = [(s, encode(s)) for s in sentences if s.strip()]

        chunks = []
        current_tokens: list[int] = []
        current_sentences: list[str] = []
        order_index = 0
        step = max(1, chunk_size - overlap)

        for sent_text, sent_toks in sentence_tokens:
            if len(current_tokens) + len(sent_toks) > chunk_size and current_tokens:
                # Emit chunk
                chunk_content = " ".join(current_sentences)
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    content=chunk_content.strip(),
                    tokens=len(current_tokens),
                    order_index=order_index,
                    metadata={"chunker": self.name, "filename": doc_filename},
                ))
                order_index += 1

                # Keep overlap worth of sentences
                if overlap > 0:
                    kept_tokens = 0
                    keep_from = len(current_sentences)
                    for i in range(len(current_sentences) - 1, -1, -1):
                        stoks = len(encode(current_sentences[i]))
                        if kept_tokens + stoks > overlap:
                            break
                        kept_tokens += stoks
                        keep_from = i
                    current_sentences = current_sentences[keep_from:]
                    current_tokens = []
                    for s in current_sentences:
                        current_tokens.extend(encode(s))
                else:
                    current_sentences = []
                    current_tokens = []

            # If a single sentence exceeds chunk_size, force-split by tokens
            if len(sent_toks) > chunk_size:
                # Flush any accumulated content first
                if current_sentences:
                    chunk_content = " ".join(current_sentences)
                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        document_id=doc_id,
                        content=chunk_content.strip(),
                        tokens=len(current_tokens),
                        order_index=order_index,
                        metadata={"chunker": self.name, "filename": doc_filename},
                    ))
                    order_index += 1
                    current_sentences = []
                    current_tokens = []

                # Split the oversized sentence by character position
                for i in range(0, len(sent_toks), step):
                    window = sent_toks[i:i + chunk_size]
                    # Approximate text from character positions
                    ratio_start = i / len(sent_toks)
                    ratio_end = min(1.0, (i + chunk_size) / len(sent_toks))
                    char_start = int(ratio_start * len(sent_text))
                    char_end = int(ratio_end * len(sent_text))
                    chunk_content = sent_text[char_start:char_end].strip()
                    if chunk_content:
                        chunks.append(Chunk(
                            id=str(uuid.uuid4()),
                            document_id=doc_id,
                            content=chunk_content,
                            tokens=len(window),
                            order_index=order_index,
                            metadata={"chunker": self.name, "filename": doc_filename},
                        ))
                        order_index += 1
                continue

            current_tokens.extend(sent_toks)
            current_sentences.append(sent_text)

        # Last chunk
        if current_sentences:
            chunk_content = " ".join(current_sentences)
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                content=chunk_content.strip(),
                tokens=len(current_tokens),
                order_index=order_index,
                metadata={"chunker": self.name, "filename": doc_filename},
            ))

        return chunks

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """Split text into sentences using simple heuristics."""
        import re
        # Split on sentence-ending punctuation followed by space/newline
        parts = re.split(r'(?<=[.!?])\s+|\n\n+|\n(?=[A-Z#\-\*\d])', text)
        return [p for p in parts if p.strip()]

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if config.get("chunk_token_size", 1200) < 50:
            errors.append("chunk_token_size must be >= 50")
        if config.get("chunk_overlap_token_size", 100) < 0:
            errors.append("chunk_overlap_token_size must be >= 0")
        return errors
