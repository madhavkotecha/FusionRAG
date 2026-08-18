"""Token-aware document chunking.

Ported from ``LightRAG/lightrag/operate.py::chunking_by_token_size``.
Uses *tiktoken* for accurate token counting with configurable chunk size
and overlap.
"""

from __future__ import annotations

import tiktoken


def chunking_by_token_size(
    content: str,
    doc_id: str,
    chunk_size: int = 1200,
    overlap: int = 100,
    encoding_name: str = "cl100k_base",
) -> list[dict]:
    """Split *content* into overlapping token-sized chunks.

    Parameters
    ----------
    content:
        The full document text to split.
    doc_id:
        A unique identifier for the source document; stored in every chunk.
    chunk_size:
        Maximum number of tokens per chunk.
    overlap:
        Number of overlapping tokens between consecutive chunks.  The step
        between chunk start positions is ``chunk_size - overlap``.
    encoding_name:
        The tiktoken encoding to use (default ``cl100k_base`` for GPT-4 /
        text-embedding-3-* models).

    Returns
    -------
    list[dict]
        Each dict has keys ``tokens``, ``content``, ``full_doc_id``, and
        ``chunk_order_index``.  Returns an empty list when *content* is
        blank.
    """
    if not content or not content.strip():
        return []

    encoder = tiktoken.get_encoding(encoding_name)
    tokens = encoder.encode(content)

    if not tokens:
        return []

    step = max(chunk_size - overlap, 1)
    chunks: list[dict] = []
    idx = 0
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoder.decode(chunk_tokens)

        chunks.append({
            "tokens": len(chunk_tokens),
            "content": chunk_text.strip(),
            "full_doc_id": doc_id,
            "chunk_order_index": idx,
        })

        idx += 1
        start += step

        # Guard against infinite loop when step >= remaining tokens
        if start >= len(tokens):
            break

    return chunks
