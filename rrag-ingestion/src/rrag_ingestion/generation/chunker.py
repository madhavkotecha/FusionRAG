"""ADR-0019: Semantic Chunking Strategy.

Single ingestion-time chunking pipeline used by all three retrieval engines.
Parameters: 1200 target tokens, 1500 hard cap, 100-token overlap.

Algorithm:
  1. Split document into sentences.
  2. Compute embeddings for a sliding window of sentences.
  3. Detect topic boundaries where cosine similarity drops below threshold.
  4. Group consecutive sentences between boundaries into chunks.
  5. Enforce token limits; merge under-size groups, split over-size ones.
  6. Emit chunks with 100-token overlap preserved at each boundary.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_CHARS = 4         # 1 token ≈ 4 characters (approximation without tiktoken)
TARGET_TOKENS = 1200
MAX_TOKENS = 1500
OVERLAP_TOKENS = 100
DEFAULT_BOUNDARY_THRESHOLD = 0.75  # cosine similarity below this → new chunk


@dataclass
class SemanticChunk:
    id: str
    content: str
    document_id: str
    chunk_index: int
    token_count: int
    metadata: dict = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _TOKEN_CHARS)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, keeping punctuation attached."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()]


def _overlap_text(sentences: list[str], overlap_tokens: int) -> str:
    """Return the last N tokens (approx.) worth of text from a sentence list."""
    overlap_chars = overlap_tokens * _TOKEN_CHARS
    combined = " ".join(sentences)
    return combined[-overlap_chars:] if len(combined) > overlap_chars else combined


class SemanticChunkingPipeline:
    """Embedding-based semantic chunker (ADR-0019).

    Uses cosine similarity between adjacent sentence-window embeddings to detect
    topic boundaries. Falls back to token-based splitting when the embedding call
    fails so ingestion never blocks on external service errors.
    """

    def __init__(
        self,
        target_tokens: int = TARGET_TOKENS,
        max_tokens: int = MAX_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
        boundary_threshold: float = DEFAULT_BOUNDARY_THRESHOLD,
        window_size: int = 3,
        llm_client: Any | None = None,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.boundary_threshold = boundary_threshold
        self.window_size = window_size
        self._llm = llm_client
        self.embedding_model = embedding_model

    # ── Embedding ─────────────────────────────────────────────────────────────

    async def _embed_windows(self, windows: list[str]) -> list[list[float]]:
        """Embed sentence windows. Returns empty list on failure → fallback."""
        if not windows:
            return []
        try:
            from rrag_ingestion.services import llm_service
            return await llm_service.embedding(windows, model=self.embedding_model)
        except Exception as e:
            logger.debug("Embedding failed during chunking, using token fallback: %s", e)
            return []

    # ── Boundary detection ────────────────────────────────────────────────────

    async def _detect_boundaries(self, sentences: list[str]) -> list[int] | None:
        """Return sentence indices where a new chunk should start (excluding 0).

        Returns None when embeddings are unavailable (caller should fall back to
        token splitting); returns [] when embeddings succeed but no topic
        boundary is found.
        """
        if len(sentences) <= 1:
            return []

        windows: list[str] = []
        for i in range(len(sentences)):
            group = sentences[max(0, i - self.window_size + 1) : i + 1]
            windows.append(" ".join(group))

        embeddings = await self._embed_windows(windows)
        if len(embeddings) != len(windows):
            return None  # embeddings unavailable → token-based fallback

        boundaries: list[int] = []
        for i in range(1, len(embeddings)):
            sim = _cosine_similarity(embeddings[i - 1], embeddings[i])
            if sim < self.boundary_threshold:
                boundaries.append(i)
        return boundaries

    # ── Token-based fallback ──────────────────────────────────────────────────

    def _token_split(self, text: str, document_id: str) -> list[SemanticChunk]:
        """Character-approximation chunker used when embeddings are unavailable."""
        target_chars = self.target_tokens * _TOKEN_CHARS
        overlap_chars = self.overlap_tokens * _TOKEN_CHARS
        chunks: list[SemanticChunk] = []
        start = idx = 0
        while start < len(text):
            end = min(start + target_chars, len(text))
            if end < len(text):
                for sep in ("\n\n", "\n", ". ", " "):
                    boundary = text.rfind(sep, start, end)
                    if boundary > start:
                        end = boundary + len(sep)
                        break
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:chunk:{idx}"))
                chunks.append(SemanticChunk(
                    id=chunk_id,
                    content=chunk_text,
                    document_id=document_id,
                    chunk_index=idx,
                    token_count=_estimate_tokens(chunk_text),
                    metadata={"char_start": start, "char_end": end, "method": "token_fallback"},
                ))
                idx += 1
            start = max(start + 1, end - overlap_chars)
        return chunks

    # ── Main chunking ─────────────────────────────────────────────────────────

    async def chunk(self, text: str, document_id: str, metadata: dict | None = None) -> list[SemanticChunk]:
        """Chunk a document text into semantically coherent pieces."""
        if not text.strip():
            return []

        sentences = _split_into_sentences(text)

        # Fast path: very short documents
        if _estimate_tokens(text) <= self.target_tokens:
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:chunk:0"))
            return [SemanticChunk(
                id=chunk_id,
                content=text.strip(),
                document_id=document_id,
                chunk_index=0,
                token_count=_estimate_tokens(text),
                metadata={"method": "single", **(metadata or {})},
            )]

        # Detect semantic boundaries
        boundaries = await self._detect_boundaries(sentences)

        # Embeddings unavailable → token-based splitting (respects target + overlap)
        if boundaries is None:
            return self._token_split(text, document_id)

        # Group sentences into segments by boundary
        segments: list[list[str]] = []
        current: list[str] = []
        for i, sent in enumerate(sentences):
            if i in boundaries and current:
                segments.append(current)
                current = []
            current.append(sent)
        if current:
            segments.append(current)

        # Build chunks with overlap, enforcing token limits
        chunks: list[SemanticChunk] = []
        overlap_carry = ""
        idx = 0

        for segment in segments:
            seg_text = (overlap_carry + " " + " ".join(segment)).strip()
            seg_tokens = _estimate_tokens(seg_text)

            # If segment exceeds hard cap, sub-split by token
            if seg_tokens > self.max_tokens:
                sub_chunks = self._token_split(seg_text, document_id)
                for sub in sub_chunks:
                    sub.chunk_index = idx
                    sub.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:chunk:{idx}"))
                    if metadata:
                        sub.metadata.update(metadata)
                    chunks.append(sub)
                    idx += 1
                overlap_carry = _overlap_text(segment, self.overlap_tokens)
                continue

            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:chunk:{idx}"))
            chunks.append(SemanticChunk(
                id=chunk_id,
                content=seg_text,
                document_id=document_id,
                chunk_index=idx,
                token_count=seg_tokens,
                metadata={"method": "semantic", **(metadata or {})},
            ))
            idx += 1
            overlap_carry = _overlap_text(segment, self.overlap_tokens)

        return chunks

    async def chunk_batch(
        self, documents: list[dict]
    ) -> dict[str, list[SemanticChunk]]:
        """Chunk multiple documents. Input: list of {id, content, metadata?}."""
        import asyncio
        results = await asyncio.gather(*[
            self.chunk(doc["content"], doc["id"], doc.get("metadata"))
            for doc in documents
        ], return_exceptions=False)
        return {doc["id"]: chunks for doc, chunks in zip(documents, results)}
