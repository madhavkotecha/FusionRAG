"""Pydantic config models for all 12 pipeline component categories.

Each model defines typed, validated configuration with defaults and constraints.
These drive both backend validation and frontend form rendering via JSON Schema export.

Research citations are included as comments for each category.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ─── 1. PARSER / DATA SOURCE ────────────────────────────────────────────────

class ParserConfig(BaseModel):
    """Configuration for document parsing and data source loading."""

    file_types: list[str] = Field(
        default=["pdf", "docx", "md", "txt", "csv", "epub", "html"],
        description="Supported file formats to parse",
    )
    pdf_engine: Literal["pymupdf", "pdfplumber", "unstructured", "docling"] = Field(
        default="pymupdf",
        description="PDF parsing engine",
    )
    ocr_enabled: bool = Field(default=False, description="Enable OCR for scanned documents")
    ocr_language: str = Field(default="eng", description="Tesseract OCR language code")
    extract_tables: bool = Field(default=True, description="Extract tables from documents")
    extract_images: bool = Field(default=False, description="Extract images from documents")

    # Web scraping
    url: str | None = Field(default=None, description="URL to scrape")
    css_selector: str | None = Field(default=None, description="CSS selector for content extraction")
    wait_for_js: bool = Field(default=False, description="Wait for JavaScript rendering")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")

    # Common
    encoding: str = Field(default="utf-8", description="File encoding")
    max_file_size_mb: int = Field(default=100, ge=1, le=1000, description="Maximum file size in MB")
    metadata_extraction: bool = Field(
        default=True,
        description="Extract document metadata (title, author, dates)",
    )


# ─── 2. CHUNKER ─────────────────────────────────────────────────────────────
# Research: Chroma 2024 (Recursive 88-89% recall), Semantic 91% recall,
# Dense X / Propositions (arXiv:2312.06648, +10 Recall@20),
# Late Chunking (arXiv:2409.04701), Anthropic Contextual Retrieval 2024 (-49% failures)

class ChunkerConfig(BaseModel):
    """Configuration for text chunking strategies."""

    # Strategy selection
    strategy: Literal[
        "recursive", "semantic", "sentence", "token", "fixed_size",
        "proposition", "late_chunking", "contextual", "hierarchical",
        "document_structure", "agentic",
    ] = Field(default="recursive", description="Chunking strategy")

    # Core sizing
    chunk_size: int = Field(
        default=512, ge=64, le=8192,
        description="Target chunk size",
        json_schema_extra={"ui_group": "core"},
    )
    chunk_overlap: int = Field(
        default=50, ge=0, le=512,
        description="Overlap between consecutive chunks",
        json_schema_extra={"ui_group": "core"},
    )
    size_unit: Literal["tokens", "characters", "words"] = Field(
        default="tokens", description="Unit for chunk_size and chunk_overlap",
    )
    min_chunk_size: int = Field(
        default=50, ge=0,
        description="Discard chunks smaller than this (same unit as size_unit)",
        json_schema_extra={"ui_group": "core"},
    )

    # Recursive-specific
    separators: list[str] = Field(
        default=["\n\n\n", "\n\n", "\n", ". ", " ", ""],
        description="Hierarchical separators from coarse to fine",
        json_schema_extra={"ui_group": "recursive", "ui_advanced": True},
    )

    # Semantic-specific (Chroma Research 2024)
    similarity_threshold: float = Field(
        default=0.80, ge=0.0, le=1.0,
        description="Cosine similarity threshold for semantic boundary detection",
        json_schema_extra={"ui_group": "semantic"},
    )
    breakpoint_type: Literal["percentile", "stddev", "interquartile"] = Field(
        default="percentile", description="Method to detect semantic boundaries",
        json_schema_extra={"ui_group": "semantic"},
    )
    breakpoint_value: float = Field(
        default=95.0,
        description="Breakpoint threshold value (95th percentile, 2.0 stddev, etc.)",
        json_schema_extra={"ui_group": "semantic"},
    )
    embedding_model_for_chunking: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model for semantic similarity computation",
        json_schema_extra={"ui_group": "semantic"},
    )
    buffer_size: int = Field(
        default=1, ge=0, le=5,
        description="Sentences of context around semantic boundary",
        json_schema_extra={"ui_group": "semantic", "ui_advanced": True},
    )

    # Sentence-specific
    min_sentences: int = Field(
        default=3, ge=1, description="Minimum sentences per chunk",
        json_schema_extra={"ui_group": "sentence"},
    )
    max_sentences: int = Field(
        default=10, ge=1, description="Maximum sentences per chunk",
        json_schema_extra={"ui_group": "sentence"},
    )

    # Token-specific
    tokenizer: str = Field(
        default="cl100k_base", description="Tiktoken encoding name",
        json_schema_extra={"ui_group": "token", "ui_advanced": True},
    )

    # Proposition-based (Dense X Retrieval, arXiv:2312.06648)
    proposition_model: str = Field(
        default="gpt-4o-mini", description="LLM for proposition decomposition",
        json_schema_extra={"ui_group": "proposition"},
    )
    decontextualize: bool = Field(
        default=True,
        description="Resolve pronouns and add context to make propositions self-contained",
        json_schema_extra={"ui_group": "proposition"},
    )

    # Late chunking (arXiv:2409.04701)
    long_context_model: str = Field(
        default="jinaai/jina-embeddings-v2-base-en",
        description="Long-context embedding model for late chunking",
        json_schema_extra={"ui_group": "late_chunking"},
    )
    pooling_strategy: Literal["mean", "cls", "attention_weighted"] = Field(
        default="mean", description="Pooling strategy for chunk embeddings",
        json_schema_extra={"ui_group": "late_chunking"},
    )

    # Contextual retrieval (Anthropic 2024)
    context_enrichment: bool = Field(
        default=False,
        description="Prepend LLM-generated context to each chunk before embedding",
        json_schema_extra={"ui_group": "contextual"},
    )
    context_model: str = Field(
        default="gpt-4o-mini", description="LLM for context generation",
        json_schema_extra={"ui_group": "contextual"},
    )
    context_prompt: str = Field(
        default="Situate this chunk within the overall document for search",
        description="Prompt template for context enrichment",
        json_schema_extra={"ui_group": "contextual", "ui_widget": "textarea"},
    )

    # Hierarchical / Small2Big
    child_chunk_size: int = Field(
        default=128, ge=32, le=2048,
        description="Small chunk size for retrieval (hierarchical mode)",
        json_schema_extra={"ui_group": "hierarchical"},
    )
    parent_chunk_size: int = Field(
        default=1024, ge=128, le=8192,
        description="Large chunk size for LLM context (hierarchical mode)",
        json_schema_extra={"ui_group": "hierarchical"},
    )
    expansion_strategy: Literal["parent", "siblings", "window"] = Field(
        default="parent", description="How to expand retrieved child chunks",
        json_schema_extra={"ui_group": "hierarchical"},
    )

    # Document structure
    respect_headers: bool = Field(
        default=True, description="Split at document headers/headings",
        json_schema_extra={"ui_group": "document_structure"},
    )
    respect_tables: bool = Field(
        default=True, description="Keep tables as atomic chunks",
        json_schema_extra={"ui_group": "document_structure"},
    )
    respect_code_blocks: bool = Field(
        default=True, description="Keep code blocks as atomic chunks",
        json_schema_extra={"ui_group": "document_structure"},
    )
    header_patterns: list[str] = Field(
        default=[r"^#{1,6}\s", r"^\d+\.\s"],
        description="Regex patterns for detecting headings",
        json_schema_extra={"ui_group": "document_structure", "ui_advanced": True},
    )
    attach_header_chain: bool = Field(
        default=True,
        description="Prepend parent heading hierarchy to each chunk",
        json_schema_extra={"ui_group": "document_structure"},
    )

    # Post-processing
    strip_whitespace: bool = Field(default=True, description="Strip whitespace from chunks")
    add_metadata: bool = Field(
        default=True,
        description="Add chunker metadata (source doc, position, etc.) to each chunk",
    )


# ─── 3. EMBEDDER ────────────────────────────────────────────────────────────
# Research: MTEB 2025 — Qwen3-Embedding-8B (70.58), BGE-M3 (dense+sparse+ColBERT),
# OpenAI text-embedding-3-small (best cost-effective), Jina-v3 (arXiv:2409.10173)

class EmbedderConfig(BaseModel):
    """Configuration for text embedding models."""

    # Model selection
    provider: Literal[
        "openai", "cohere", "voyage", "local", "jina", "nomic", "google",
    ] = Field(default="openai", description="Embedding provider")
    model_name: str = Field(
        default="text-embedding-3-small", description="Embedding model identifier",
    )

    # Dimensions (Matryoshka support — 2-4x storage savings with <2% quality loss)
    dimensions: int | None = Field(
        default=None,
        description="Output dimensions (None=model default; set for Matryoshka truncation)",
        json_schema_extra={"ui_group": "model"},
    )

    # Batching
    batch_size: int = Field(
        default=100, ge=1, le=2048, description="Texts per API/inference batch",
    )
    max_retries: int = Field(default=3, ge=0, description="API retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, description="Delay between retries in seconds")

    # Instruction prefixes (critical for asymmetric retrieval — E5, Nomic, BGE)
    query_prefix: str = Field(
        default="",
        description="Prefix for query texts (e.g., 'query: ' for E5, 'search_query: ' for Nomic)",
        json_schema_extra={"ui_group": "prefixes"},
    )
    document_prefix: str = Field(
        default="",
        description="Prefix for document texts (e.g., 'passage: ' for E5)",
        json_schema_extra={"ui_group": "prefixes"},
    )

    # Cohere-specific
    input_type: Literal[
        "search_document", "search_query", "classification", "clustering",
    ] | None = Field(
        default=None,
        description="Cohere input_type (required for Cohere embed-v3+)",
        json_schema_extra={"ui_group": "cohere"},
    )

    # Jina-specific (LoRA task adapters, arXiv:2409.10173)
    task: Literal[
        "retrieval.query", "retrieval.passage", "separation",
        "classification", "text-matching",
    ] | None = Field(
        default=None,
        description="Jina LoRA task adapter selection",
        json_schema_extra={"ui_group": "jina"},
    )

    # Local model options
    device: Literal["cpu", "cuda", "mps", "auto"] = Field(
        default="auto", description="Compute device for local models",
        json_schema_extra={"ui_group": "local", "ui_advanced": True},
    )
    normalize: bool = Field(
        default=True, description="L2-normalize output embeddings",
        json_schema_extra={"ui_advanced": True},
    )
    truncation_strategy: Literal["none", "start", "end"] = Field(
        default="end", description="How to truncate texts exceeding max tokens",
        json_schema_extra={"ui_advanced": True},
    )

    # Output format
    encoding_format: Literal["float32", "float16", "int8", "binary"] = Field(
        default="float32", description="Output encoding format",
        json_schema_extra={"ui_advanced": True},
    )
    show_progress: bool = Field(default=True, description="Show embedding progress bar")


# ─── 4. EXTRACTOR ───────────────────────────────────────────────────────────
# Research: KGGen (NeurIPS 2025, arXiv:2502.09956) 66% accuracy vs GraphRAG 48%.
# Schema-based = better precision; Schema-free = better recall.

class ExtractorConfig(BaseModel):
    """Configuration for entity and relation extraction."""

    # Mode
    extraction_mode: Literal["llm", "ner_model", "hybrid"] = Field(
        default="llm", description="Extraction approach",
    )
    schema_mode: Literal["schema_free", "schema_constrained", "auto_schema"] = Field(
        default="schema_free",
        description="Schema-free (open extraction) vs schema-constrained (guided by ontology)",
    )

    # LLM settings
    llm_model: str = Field(default="gpt-4o-mini", description="LLM for extraction")

    # NER model (for ner_model/hybrid modes)
    ner_model: str = Field(
        default="en_core_web_trf",
        description="SpaCy or HuggingFace NER model",
        json_schema_extra={"ui_group": "ner"},
    )

    # Entity & relation types
    entity_types: list[str] = Field(
        default=["Person", "Organization", "Location", "Concept", "Event", "Technology"],
        description="Allowed entity types (empty=auto-detect)",
    )
    relation_types: list[str] = Field(
        default=[],
        description="Allowed relation types (empty=auto-detect)",
    )

    # Schema definition (for constrained mode)
    extraction_schema: dict | None = Field(
        default=None,
        description="Domain ontology definition (entity types, relation types, constraints)",
        json_schema_extra={"ui_widget": "json", "ui_group": "schema"},
    )

    # Quality controls
    max_gleaning: int = Field(
        default=1, ge=0, le=5,
        description="Re-extraction passes for missed entities (LightRAG-style gleaning)",
    )
    confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Minimum confidence score to keep an extraction",
    )
    max_entities_per_chunk: int = Field(default=20, ge=1, description="Max entities per chunk")
    max_relations_per_chunk: int = Field(default=30, ge=1, description="Max relations per chunk")

    # Coreference & deduplication
    resolve_coreferences: bool = Field(
        default=True, description="Resolve pronouns to their referent entities",
    )
    merge_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Embedding similarity threshold for merging duplicate entities",
    )

    # Processing
    batch_size: int = Field(default=10, ge=1, description="Chunks per extraction batch")
    include_descriptions: bool = Field(
        default=True, description="Include entity/relation descriptions",
    )
    include_source_spans: bool = Field(
        default=True, description="Include source text spans for each extraction",
    )


# ─── 5. GRAPH BUILDER ──────────────────────────────────────────────────────
# Research: Microsoft GraphRAG (Leiden community detection),
# KGGen iterative clustering (arXiv:2502.09956), entity resolution is #1 factor.

class GraphBuilderConfig(BaseModel):
    """Configuration for knowledge graph construction."""

    # Entity resolution
    entity_resolution_mode: Literal[
        "exact", "fuzzy", "embedding", "llm", "hybrid",
    ] = Field(default="embedding", description="Entity deduplication approach")
    dedup_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Embedding cosine similarity threshold for entity merging",
    )
    fuzzy_match_threshold: float = Field(
        default=0.9, ge=0.0, le=1.0,
        description="Fuzzy string match threshold (Levenshtein ratio)",
        json_schema_extra={"ui_advanced": True},
    )
    resolution_model: str = Field(
        default="gpt-4o-mini",
        description="LLM for entity resolution (llm/hybrid modes)",
        json_schema_extra={"ui_group": "resolution"},
    )
    clustering_rounds: int = Field(
        default=3, ge=1, le=10,
        description="Iterative clustering rounds for entity resolution",
        json_schema_extra={"ui_advanced": True},
    )

    # Merge strategy
    merge_strategy: Literal[
        "merge_descriptions", "keep_latest", "keep_highest_score", "summarize",
    ] = Field(default="merge_descriptions", description="How to merge duplicate entities")

    # Community detection (GraphRAG-style)
    community_algorithm: Literal[
        "leiden", "louvain", "label_propagation", "none",
    ] = Field(default="leiden", description="Community detection algorithm")
    community_resolution: float = Field(
        default=1.0, ge=0.1, le=10.0,
        description="Resolution parameter (higher=smaller communities)",
        json_schema_extra={"ui_group": "community"},
    )
    min_community_size: int = Field(
        default=5, ge=2, description="Minimum nodes per community",
        json_schema_extra={"ui_group": "community"},
    )
    max_hierarchy_levels: int = Field(
        default=3, ge=1, le=10,
        description="Max levels in community hierarchy",
        json_schema_extra={"ui_group": "community"},
    )
    generate_community_summaries: bool = Field(
        default=True,
        description="Generate LLM summaries for each community (GraphRAG-style)",
        json_schema_extra={"ui_group": "community"},
    )
    summary_model: str = Field(
        default="gpt-4o-mini",
        description="LLM for community summary generation",
        json_schema_extra={"ui_group": "community"},
    )

    # Linking
    add_chunk_links: bool = Field(
        default=True, description="Link chunks to their extracted entities",
    )
    edge_weight_mode: Literal["frequency", "confidence", "uniform"] = Field(
        default="frequency", description="How to compute edge weights",
        json_schema_extra={"ui_advanced": True},
    )

    # Incremental updates
    incremental: bool = Field(
        default=True, description="Enable incremental graph updates",
    )
    conflict_resolution: Literal["keep_both", "keep_latest", "merge"] = Field(
        default="keep_both", description="How to handle conflicting entities on update",
        json_schema_extra={"ui_advanced": True},
    )


# ─── 6. INDEXER ─────────────────────────────────────────────────────────────
# Research: FAISS HNSW M=16, efConstruction=128 → 97-99% recall.
# >1M vectors: IVF-PQ or Milvus DiskANN.

class IndexerConfig(BaseModel):
    """Configuration for vector index construction."""

    # Backend
    backend: Literal["faiss", "milvus", "pgvector", "qdrant", "chroma", "opensearch"] = Field(
        default="faiss", description="Vector database backend",
    )

    # Index type
    index_type: Literal["flat", "ivf_flat", "ivf_pq", "hnsw", "diskann"] = Field(
        default="hnsw", description="Index algorithm",
    )
    distance_metric: Literal["cosine", "l2", "inner_product"] = Field(
        default="cosine", description="Distance metric for similarity search",
    )
    dimension: int = Field(
        default=1536, ge=1,
        description="Embedding vector dimension (must match embedder output)",
    )

    # HNSW parameters
    hnsw_m: int = Field(
        default=16, ge=4, le=64,
        description="Max bi-directional connections per node",
        json_schema_extra={"ui_group": "hnsw"},
    )
    hnsw_ef_construction: int = Field(
        default=128, ge=16, le=512,
        description="Build-time search width (higher=better index, slower build)",
        json_schema_extra={"ui_group": "hnsw"},
    )
    hnsw_ef_search: int = Field(
        default=64, ge=16, le=512,
        description="Query-time search width (higher=better recall, slower query)",
        json_schema_extra={"ui_group": "hnsw"},
    )

    # IVF parameters
    nlist: int = Field(
        default=1024, ge=1,
        description="Number of Voronoi cells (IVF). Rule: 4*sqrt(N) to 16*sqrt(N)",
        json_schema_extra={"ui_group": "ivf"},
    )
    nprobe: int = Field(
        default=64, ge=1,
        description="Cells to probe at query time (higher=better recall)",
        json_schema_extra={"ui_group": "ivf"},
    )

    # PQ parameters
    pq_m: int = Field(
        default=8, ge=1,
        description="Number of sub-quantizers (PQ compression)",
        json_schema_extra={"ui_group": "pq", "ui_advanced": True},
    )
    pq_nbits: int = Field(
        default=8, ge=1, le=16,
        description="Bits per sub-quantizer code",
        json_schema_extra={"ui_group": "pq", "ui_advanced": True},
    )

    # Processing
    normalize_vectors: bool = Field(
        default=True, description="L2-normalize vectors before indexing",
    )
    batch_size: int = Field(default=1000, ge=1, description="Vectors per indexing batch")
    num_threads: int = Field(
        default=4, ge=1, description="Parallel threads for index construction",
        json_schema_extra={"ui_advanced": True},
    )

    # Persistence
    index_path: str = Field(default="./data/index", description="Path to save/load index")
    overwrite: bool = Field(default=False, description="Overwrite existing index")

    # Milvus-specific
    uri: str = Field(
        default="http://localhost:19530", description="Milvus server URI",
        json_schema_extra={"ui_group": "milvus"},
    )
    collection_name: str = Field(
        default="rrag_default", description="Milvus collection name",
        json_schema_extra={"ui_group": "milvus"},
    )


# ─── 7. RETRIEVER ──────────────────────────────────────────────────────────
# Research: Hybrid (dense+BM25) → +26-31% NDCG (ACM TOIS).
# ColBERTv2 (arXiv:2112.01488), HippoRAG (NeurIPS 2024).

class RetrieverConfig(BaseModel):
    """Configuration for document retrieval."""

    # Strategy
    strategy: Literal[
        "dense", "sparse", "hybrid", "colbert", "graph", "web", "multi_vector",
    ] = Field(default="dense", description="Retrieval strategy")

    # Core
    top_k: int = Field(
        default=20, ge=1, le=1000, description="Number of documents to retrieve",
    )
    score_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Minimum similarity score to include a result",
        json_schema_extra={"ui_advanced": True},
    )

    # Dense retrieval
    embedding_model: str = Field(
        default="openai",
        description="Embedding model for query encoding",
        json_schema_extra={"ui_group": "dense"},
    )
    index_path: str = Field(
        default="./data/faiss_index",
        description="Path to vector index",
        json_schema_extra={"ui_group": "dense"},
    )
    query_prefix: str = Field(
        default="", description="Prefix for query embedding",
        json_schema_extra={"ui_group": "dense"},
    )

    # Sparse (BM25)
    bm25_k1: float = Field(
        default=1.2, ge=0.0, le=3.0,
        description="BM25 term frequency saturation",
        json_schema_extra={"ui_group": "sparse"},
    )
    bm25_b: float = Field(
        default=0.75, ge=0.0, le=1.0,
        description="BM25 document length normalization",
        json_schema_extra={"ui_group": "sparse"},
    )

    # Hybrid fusion
    alpha: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Dense weight (1.0=all dense, 0.0=all sparse). Optimal: 0.6-0.7",
        json_schema_extra={"ui_group": "hybrid"},
    )
    fusion_method: Literal["rrf", "weighted_sum", "convex_combination"] = Field(
        default="rrf", description="Score fusion method",
        json_schema_extra={"ui_group": "hybrid"},
    )
    rrf_k: int = Field(
        default=60, ge=1,
        description="RRF smoothing constant. score = 1/(rank + k)",
        json_schema_extra={"ui_group": "hybrid"},
    )
    normalize_scores: bool = Field(
        default=True,
        description="Normalize scores before fusion (required for weighted_sum)",
        json_schema_extra={"ui_group": "hybrid", "ui_advanced": True},
    )

    # Diversity (MMR)
    use_mmr: bool = Field(
        default=False, description="Apply Maximal Marginal Relevance for diversity",
        json_schema_extra={"ui_group": "diversity"},
    )
    mmr_lambda: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="MMR trade-off: 1.0=pure relevance, 0.0=maximum diversity",
        json_schema_extra={"ui_group": "diversity"},
    )
    mmr_fetch_k: int = Field(
        default=50, ge=1,
        description="Candidate pool size for MMR (should be > top_k)",
        json_schema_extra={"ui_group": "diversity", "ui_advanced": True},
    )

    # Graph retrieval
    graph_uri: str = Field(
        default="bolt://localhost:7687", description="Neo4j URI for graph retrieval",
        json_schema_extra={"ui_group": "graph"},
    )
    graph_search_depth: int = Field(
        default=2, ge=1, le=5,
        description="Max traversal hops in knowledge graph",
        json_schema_extra={"ui_group": "graph"},
    )
    community_level: int = Field(
        default=0, ge=0,
        description="GraphRAG community hierarchy level (0=leaf)",
        json_schema_extra={"ui_group": "graph", "ui_advanced": True},
    )

    # Web retrieval
    search_engine: Literal["duckduckgo", "serper", "tavily", "brave"] = Field(
        default="duckduckgo", description="Web search provider",
        json_schema_extra={"ui_group": "web"},
    )
    max_web_results: int = Field(
        default=5, ge=1, description="Maximum web search results",
        json_schema_extra={"ui_group": "web"},
    )

    # ColBERT (arXiv:2112.01488)
    colbert_model: str = Field(
        default="colbert-ir/colbertv2.0", description="ColBERT model",
        json_schema_extra={"ui_group": "colbert"},
    )
    ncells: int = Field(
        default=2, ge=1,
        description="IVF cells to probe per query token",
        json_schema_extra={"ui_group": "colbert", "ui_advanced": True},
    )
    ndocs: int = Field(
        default=256, ge=1,
        description="Max candidate documents before exact scoring",
        json_schema_extra={"ui_group": "colbert", "ui_advanced": True},
    )


# ─── 8. RERANKER ───────────────────────────────────────────────────────────
# Research: BGE-reranker-v2-m3 (best open-source multilingual),
# Jina-Reranker-v3 (arXiv:2509.25085, highest BEIR nDCG@10 = 61.94),
# RankZephyr (arXiv:2312.02724, matches GPT-4 at fraction of cost)

class RerankerConfig(BaseModel):
    """Configuration for document reranking."""

    # Strategy
    strategy: Literal[
        "cross_encoder", "colbert", "llm_listwise", "cohere", "jina",
    ] = Field(default="cross_encoder", description="Reranking strategy")

    # Model
    model_name: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Reranker model identifier",
    )

    # Output
    top_k: int = Field(
        default=10, ge=1, description="Documents to return after reranking",
    )
    score_threshold: float = Field(
        default=0.0, ge=-1.0, le=1.0,
        description="Minimum relevance score to keep",
    )

    # Cross-encoder settings
    max_length: int = Field(
        default=512, ge=128, le=8192,
        description="Max input tokens per query-document pair",
        json_schema_extra={"ui_group": "cross_encoder"},
    )
    batch_size: int = Field(
        default=32, ge=1,
        description="Pairs per inference batch",
        json_schema_extra={"ui_group": "cross_encoder"},
    )
    device: Literal["cpu", "cuda", "mps", "auto"] = Field(
        default="auto", description="Compute device",
        json_schema_extra={"ui_group": "cross_encoder", "ui_advanced": True},
    )

    # LLM listwise (RankGPT/RankZephyr-style)
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM for listwise reranking",
        json_schema_extra={"ui_group": "llm_listwise"},
    )
    window_size: int = Field(
        default=20, ge=5,
        description="Documents per sliding window pass",
        json_schema_extra={"ui_group": "llm_listwise"},
    )
    step_size: int = Field(
        default=10, ge=1,
        description="Stride for sliding window",
        json_schema_extra={"ui_group": "llm_listwise"},
    )
    num_passes: int = Field(
        default=1, ge=1, le=3,
        description="Number of reranking passes (more=better quality, slower)",
        json_schema_extra={"ui_group": "llm_listwise"},
    )


# ─── 9. GENERATOR ──────────────────────────────────────────────────────────
# Research: Temperature 0.1-0.3 for factual RAG (arXiv:2512.01183),
# relevance-first context ordering, citation modes improve faithfulness,
# RAGCHECKER (NeurIPS 2024)

class GeneratorConfig(BaseModel):
    """Configuration for RAG answer generation."""

    # Model
    model: str = Field(default="gpt-4o-mini", description="LLM model identifier")
    provider: Literal[
        "openai", "anthropic", "local", "groq", "together",
    ] = Field(default="openai", description="LLM provider")

    # Sampling
    temperature: float = Field(
        default=0.2, ge=0.0, le=2.0,
        description="Sampling temperature. Use 0.1-0.3 for factual RAG",
    )
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling threshold")
    max_tokens: int = Field(default=2048, ge=1, le=128000, description="Maximum output tokens")
    frequency_penalty: float = Field(
        default=0.1, ge=-2.0, le=2.0,
        description="Penalize repeated tokens (avoids verbatim chunk regurgitation)",
        json_schema_extra={"ui_advanced": True},
    )
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0,
        description="Penalize tokens already present",
        json_schema_extra={"ui_advanced": True},
    )

    # Prompt
    system_prompt: str = Field(
        default="You are a helpful assistant. Answer based on the provided context. If the context doesn't contain the answer, say so.",
        description="System prompt for the LLM",
        json_schema_extra={"ui_widget": "textarea"},
    )

    # Citation handling
    citation_mode: Literal[
        "none", "inline", "footnote", "structured", "quote_grounding",
    ] = Field(
        default="inline",
        description="How to handle source citations in the response",
        json_schema_extra={"ui_group": "citation"},
    )

    # Context management
    context_ordering: Literal[
        "relevance_first", "recency_first", "sandwich", "random",
    ] = Field(
        default="relevance_first",
        description="Order of retrieved documents in the prompt",
        json_schema_extra={"ui_group": "context"},
    )
    context_max_tokens: int = Field(
        default=8000, ge=100,
        description="Maximum tokens reserved for retrieved context",
        json_schema_extra={"ui_group": "context"},
    )
    context_template: str = Field(
        default="[Document {index}] (score: {score})\n{content}",
        description="Template for formatting each context document",
        json_schema_extra={"ui_group": "context", "ui_advanced": True},
    )

    # Chain-of-thought
    enable_cot: bool = Field(
        default=False,
        description="Enable chain-of-thought reasoning before answering",
        json_schema_extra={"ui_group": "reasoning"},
    )
    cot_instruction: str = Field(
        default="Think step by step before answering.",
        description="Instruction appended when CoT is enabled",
        json_schema_extra={"ui_group": "reasoning", "ui_advanced": True},
    )

    # Output
    response_format: Literal["text", "json", "markdown"] = Field(
        default="text", description="Expected response format",
    )
    stream: bool = Field(default=True, description="Stream the response")

    # Faithfulness
    faithfulness_instruction: str = Field(
        default="Only use information from the provided context. Cite your sources.",
        description="Instruction to improve answer faithfulness",
        json_schema_extra={"ui_advanced": True, "ui_widget": "textarea"},
    )


# ─── 10. PLANNER ───────────────────────────────────────────────────────────
# Research: CoRAG (arXiv:2501.14342), MCTS-RAG (arXiv:2503.20757, +20%),
# Self-RAG (arXiv:2310.11511, ICLR 2024), IRCoT (interleaved reasoning)

class PlannerConfig(BaseModel):
    """Configuration for query planning and decomposition."""

    # Strategy
    strategy: Literal[
        "corag", "ircot", "self_rag", "mcts", "plan_and_execute", "tree_of_thought",
    ] = Field(default="corag", description="Planning strategy")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM for planning")

    # Hop control
    max_hops: int = Field(
        default=3, ge=1, le=10,
        description="Maximum retrieval hops (sub-queries)",
    )
    max_reasoning_steps: int = Field(
        default=5, ge=1, le=20,
        description="Maximum reasoning steps per hop",
        json_schema_extra={"ui_advanced": True},
    )

    # Search method
    search_method: Literal[
        "greedy", "best_of_n", "beam", "mcts", "tree_search",
    ] = Field(default="greedy", description="Search strategy for plan exploration")
    beam_width: int = Field(
        default=3, ge=1,
        description="Beam width (for beam search)",
        json_schema_extra={"ui_group": "search", "ui_advanced": True},
    )
    n_samples: int = Field(
        default=5, ge=1,
        description="Number of candidate samples (for best_of_n)",
        json_schema_extra={"ui_group": "search", "ui_advanced": True},
    )

    # MCTS parameters (arXiv:2503.20757)
    mcts_simulations: int = Field(
        default=100, ge=10,
        description="MCTS simulation budget",
        json_schema_extra={"ui_group": "mcts"},
    )
    mcts_exploration_constant: float = Field(
        default=1.414, ge=0.0,
        description="UCT exploration constant (sqrt(2) is standard)",
        json_schema_extra={"ui_group": "mcts", "ui_advanced": True},
    )
    max_depth: int = Field(
        default=5, ge=1,
        description="Maximum tree depth for MCTS/tree_search",
        json_schema_extra={"ui_group": "mcts"},
    )

    # Retrieval integration
    reformulation_enabled: bool = Field(
        default=True,
        description="Allow query reformulation between hops",
    )
    retrieval_trigger: Literal["every_step", "on_uncertainty", "adaptive"] = Field(
        default="every_step",
        description="When to trigger retrieval during reasoning",
    )

    # Self-RAG reflection (arXiv:2310.11511)
    reflection_enabled: bool = Field(
        default=False,
        description="Enable Self-RAG reflection tokens (ISREL, ISSUP, ISUSE)",
        json_schema_extra={"ui_group": "reflection"},
    )
    relevance_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Minimum relevance score for retrieved passages",
        json_schema_extra={"ui_group": "reflection"},
    )
    support_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Minimum support score for generated claims",
        json_schema_extra={"ui_group": "reflection"},
    )

    # Quality
    confidence_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Minimum confidence to accept a plan step",
        json_schema_extra={"ui_advanced": True},
    )
    backtracking_enabled: bool = Field(
        default=True,
        description="Allow backtracking on contradictions (RT-RAG style)",
    )
    max_retries: int = Field(default=3, ge=0, description="Max retry attempts per hop")

    # Output format
    plan_format: Literal["sequential", "dag", "tree"] = Field(
        default="sequential", description="Output plan structure",
    )

    # KAG-specific operators
    operators: list[str] = Field(
        default=["kg_retrieval", "text_retrieval", "math", "deduce"],
        description="Available operators for KAG planning",
        json_schema_extra={"ui_group": "kag"},
    )


# ─── 11. AGENT ──────────────────────────────────────────────────────────────
# Research: Agentic RAG Survey (arXiv:2501.09136),
# CRAG (arXiv:2401.15884), A-Mem (arXiv:2502.12110)

class AgentConfig(BaseModel):
    """Configuration for agentic RAG components."""

    # Type
    agent_type: Literal[
        "router", "reflection", "memory", "tool_use", "orchestrator",
    ] = Field(default="router", description="Agent type")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM for agent reasoning")

    # Router (CRAG / Adaptive-RAG)
    routing_mode: Literal["adaptive", "rule_based", "llm_classifier"] = Field(
        default="adaptive", description="Query routing approach",
        json_schema_extra={"ui_group": "router"},
    )
    available_strategies: list[str] = Field(
        default=["dense", "hybrid", "graph", "web"],
        description="Available retrieval strategies for routing",
        json_schema_extra={"ui_group": "router"},
    )
    confidence_upper_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Above this = high confidence, use direct retrieval",
        json_schema_extra={"ui_group": "router"},
    )
    confidence_lower_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Below this = low confidence, use web search fallback",
        json_schema_extra={"ui_group": "router"},
    )
    fallback_strategy: str = Field(
        default="web_search",
        description="Fallback when confidence is below lower threshold",
        json_schema_extra={"ui_group": "router"},
    )

    # Reflection (Self-RAG, RAG-HAT)
    min_quality_score: float = Field(
        default=6.0, ge=0.0, le=10.0,
        description="Minimum response quality score to accept (1-10 scale)",
        json_schema_extra={"ui_group": "reflection"},
    )
    max_retries: int = Field(
        default=3, ge=0,
        description="Maximum retry attempts on low quality",
        json_schema_extra={"ui_group": "reflection"},
    )
    critique_dimensions: list[str] = Field(
        default=["faithfulness", "relevance", "completeness", "coherence"],
        description="Dimensions to evaluate in response critique",
        json_schema_extra={"ui_group": "reflection"},
    )
    hallucination_detection: Literal[
        "llm_judge", "nli_model", "self_consistency", "none",
    ] = Field(
        default="llm_judge",
        description="Hallucination detection method",
        json_schema_extra={"ui_group": "reflection"},
    )

    # Memory (A-Mem, MemR3)
    memory_type: Literal[
        "conversation", "episodic", "semantic", "working",
    ] = Field(
        default="conversation", description="Memory architecture type",
        json_schema_extra={"ui_group": "memory"},
    )
    max_history_turns: int = Field(
        default=20, ge=1,
        description="Maximum conversation turns to keep",
        json_schema_extra={"ui_group": "memory"},
    )
    summarization_enabled: bool = Field(
        default=True,
        description="Summarize old conversation turns to save tokens",
        json_schema_extra={"ui_group": "memory"},
    )
    importance_scoring: bool = Field(
        default=True,
        description="Score memory items by importance for selective retention",
        json_schema_extra={"ui_group": "memory"},
    )
    decay_rate: float = Field(
        default=0.95, ge=0.0, le=1.0,
        description="Memory decay factor (lower=faster forgetting)",
        json_schema_extra={"ui_group": "memory", "ui_advanced": True},
    )
    max_memory_tokens: int = Field(
        default=4000, ge=100,
        description="Maximum tokens for memory context",
        json_schema_extra={"ui_group": "memory"},
    )

    # Tool use
    available_tools: list[str] = Field(
        default=[],
        description="Available tool names for the agent",
        json_schema_extra={"ui_group": "tool_use"},
    )
    max_tool_calls: int = Field(
        default=5, ge=1,
        description="Maximum tool calls per agent turn",
        json_schema_extra={"ui_group": "tool_use"},
    )
    tool_selection_mode: Literal["llm", "rule_based"] = Field(
        default="llm", description="How tools are selected",
        json_schema_extra={"ui_group": "tool_use"},
    )

    # Orchestrator
    max_iterations: int = Field(
        default=10, ge=1,
        description="Maximum orchestration iterations",
        json_schema_extra={"ui_group": "orchestrator"},
    )
    convergence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Quality threshold for orchestrator convergence",
        json_schema_extra={"ui_group": "orchestrator"},
    )


# ─── 12. STORAGE ───────────────────────────────────────────────────────────

class StorageConfig(BaseModel):
    """Configuration for data persistence backends."""

    # Backend type
    storage_type: Literal["vector", "graph", "kv", "document"] = Field(
        default="vector", description="Storage backend type",
    )

    # Vector store
    vector_backend: Literal["faiss", "milvus", "pgvector", "qdrant", "chroma"] = Field(
        default="faiss", description="Vector storage backend",
        json_schema_extra={"ui_group": "vector"},
    )
    collection_name: str = Field(
        default="rrag_default", description="Collection/index name",
        json_schema_extra={"ui_group": "vector"},
    )

    # Graph store
    graph_backend: Literal["neo4j", "neptune", "memgraph"] = Field(
        default="neo4j", description="Graph database backend",
        json_schema_extra={"ui_group": "graph"},
    )
    graph_uri: str = Field(
        default="bolt://localhost:7687", description="Graph database URI",
        json_schema_extra={"ui_group": "graph"},
    )
    graph_username: str = Field(
        default="neo4j", description="Graph database username",
        json_schema_extra={"ui_group": "graph"},
    )
    graph_password: str = Field(
        default="", description="Graph database password (use env vars in production)",
        json_schema_extra={"ui_group": "graph", "ui_widget": "password"},
    )

    # KV store
    kv_backend: Literal["redis", "memcached", "dynamodb"] = Field(
        default="redis", description="Key-value store backend",
        json_schema_extra={"ui_group": "kv"},
    )
    key_prefix: str = Field(
        default="rrag:", description="Key prefix for namespacing",
        json_schema_extra={"ui_group": "kv"},
    )
    ttl_seconds: int = Field(
        default=0, ge=0,
        description="Time-to-live in seconds (0=no expiry)",
        json_schema_extra={"ui_group": "kv"},
    )

    # Common
    batch_size: int = Field(default=100, ge=1, description="Items per storage batch")
    upsert: bool = Field(default=True, description="Insert or update existing entries")

    # Connection
    uri: str = Field(default="", description="Connection URI (overrides backend-specific)")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Connection timeout")


# ─── Export mapping for programmatic access ──────────────────────────────────

CONFIG_MODELS = {
    "parser": ParserConfig,
    "chunker": ChunkerConfig,
    "embedder": EmbedderConfig,
    "extractor": ExtractorConfig,
    "graph_builder": GraphBuilderConfig,
    "indexer": IndexerConfig,
    "retriever": RetrieverConfig,
    "reranker": RerankerConfig,
    "generator": GeneratorConfig,
    "planner": PlannerConfig,
    "agent": AgentConfig,
    "storage": StorageConfig,
}


def get_config_schema(category: str) -> dict:
    """Return the JSON Schema for a component category's configuration."""
    model = CONFIG_MODELS.get(category)
    if not model:
        raise ValueError(f"Unknown category: {category}. Valid: {list(CONFIG_MODELS.keys())}")
    return model.model_json_schema()
