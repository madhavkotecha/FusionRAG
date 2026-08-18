"""LightRAG utilities and composite components for the pipeline service.

This package ports core LightRAG logic into reusable, workspace-scoped
utilities and exposes three composite components:

* LightRAGIngestion   -- document chunking, entity extraction, graph storage
* LightRAGRetrieval   -- keyword extraction, KG/vector search, answer generation
* AgenticRAGRetrieval -- agent loop with tool-based retrieval strategy
"""

from .chunking import chunking_by_token_size
from .extraction import llm_extract_entities_and_relations
from .merging import merge_entities_by_similarity, merge_relations
from .context_builder import build_context

__all__ = [
    "chunking_by_token_size",
    "llm_extract_entities_and_relations",
    "merge_entities_by_similarity",
    "merge_relations",
    "build_context",
]
