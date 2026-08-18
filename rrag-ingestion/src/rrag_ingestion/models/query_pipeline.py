"""QueryPipeline model – defines how to query a DataStore.

Expanded with research-backed retriever, reranker, and generator configs
that support the full range of strategies from the visual pipeline editor.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RetrieverConfig(BaseModel):
    """Retrieval configuration with support for dense, sparse, hybrid, graph, and web strategies."""

    strategy: Literal["dense", "sparse", "hybrid", "colbert", "graph", "web", "multi_vector"] = Field(
        "dense", description="Retrieval strategy"
    )
    top_k: int = Field(20, ge=1, le=1000, description="Documents to retrieve")
    score_threshold: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score")

    # Dense retrieval
    embedding_model: str = Field("openai", description="Embedding model/provider for queries")
    query_prefix: str = Field("", description="Prefix for query embedding (e.g. 'query: ' for E5)")

    # Sparse / BM25
    bm25_k1: float = Field(1.2, ge=0.0, le=3.0, description="BM25 term frequency saturation")
    bm25_b: float = Field(0.75, ge=0.0, le=1.0, description="BM25 length normalization")

    # Hybrid fusion
    alpha: float = Field(0.6, ge=0.0, le=1.0, description="Dense weight (1.0=all dense, 0.0=all sparse)")
    fusion_method: Literal["rrf", "weighted_sum", "convex_combination"] = Field(
        "rrf", description="Score fusion method"
    )
    rrf_k: int = Field(60, ge=1, description="RRF constant")

    # Diversity (MMR)
    use_mmr: bool = Field(False, description="Apply Maximal Marginal Relevance")
    mmr_lambda: float = Field(0.5, ge=0.0, le=1.0, description="MMR lambda (1.0=relevance, 0.0=diversity)")
    mmr_fetch_k: int = Field(50, ge=1, description="Candidates for MMR reranking")

    # Graph retrieval
    graph_search_depth: int = Field(2, ge=1, le=5, description="Graph traversal depth")
    community_level: int = Field(0, ge=0, description="GraphRAG community hierarchy level")

    # Web retrieval
    search_engine: Literal["duckduckgo", "serper", "tavily", "brave"] = Field(
        "duckduckgo", description="Web search engine"
    )
    max_web_results: int = Field(5, ge=1, description="Max web search results")


class RerankerConfig(BaseModel):
    """Reranking configuration — cross-encoder, Cohere, Jina, or LLM listwise."""

    enabled: bool = Field(False, description="Enable reranking step")
    strategy: Literal["cross_encoder", "colbert", "llm_listwise", "cohere", "jina"] = Field(
        "cross_encoder", description="Reranking strategy"
    )
    model: str = Field(
        "cross-encoder/ms-marco-MiniLM-L-6-v2", description="Reranker model"
    )
    top_k: int = Field(10, ge=1, description="Documents to return after reranking")
    score_threshold: float = Field(0.0, ge=-1.0, le=1.0, description="Minimum reranker score")

    # Cross-encoder
    max_length: int = Field(512, ge=128, le=8192, description="Max input tokens")
    batch_size: int = Field(32, ge=1, description="Inference batch size")

    # LLM listwise (RankGPT-style)
    llm_model: str = Field("gpt-4o-mini", description="LLM for listwise reranking")
    window_size: int = Field(20, ge=5, description="Documents per sliding window")
    step_size: int = Field(10, ge=1, description="Stride for sliding window")


class GeneratorConfig(BaseModel):
    """LLM generation configuration with citation and context management."""

    model: str = Field("gpt-4o-mini", description="LLM model for generation")
    provider: Literal["openai", "anthropic", "local", "groq", "together"] = Field(
        "openai", description="LLM provider"
    )
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature (low for factual RAG)")
    max_tokens: int = Field(2048, ge=1, le=128000, description="Max output tokens")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Nucleus sampling")
    system_prompt: str = Field(
        "You are a helpful research assistant. Answer questions accurately based on "
        "the provided context. If you don't have enough context, say so clearly. "
        "Cite document numbers when referencing sources.",
        description="System prompt for the generator",
    )

    # Citation
    citation_mode: Literal["none", "inline", "footnote", "structured"] = Field(
        "inline", description="How to cite sources in the answer"
    )

    # Context management
    context_ordering: Literal["relevance_first", "recency_first", "sandwich", "random"] = Field(
        "relevance_first", description="Order of context chunks"
    )
    context_max_tokens: int = Field(8000, ge=100, description="Max tokens reserved for context")
    context_template: str = Field(
        "[Document {index}] (score: {score})\n{content}",
        description="Template for formatting each context chunk",
    )

    # Chain-of-thought
    enable_cot: bool = Field(False, description="Enable chain-of-thought reasoning")

    # Output
    response_format: Literal["text", "json", "markdown"] = Field("text", description="Response format")
    stream: bool = Field(True, description="Stream the response")


class PlannerConfig(BaseModel):
    """Optional planner for multi-hop retrieval."""

    enabled: bool = Field(False, description="Enable planning step")
    strategy: Literal["corag", "ircot", "self_rag", "mcts", "plan_and_execute"] = Field(
        "corag", description="Planning strategy"
    )
    llm_model: str = Field("gpt-4o-mini", description="LLM for planning")
    max_hops: int = Field(3, ge=1, le=10, description="Maximum retrieval hops")
    search_method: Literal["greedy", "best_of_n", "beam", "mcts"] = Field(
        "greedy", description="Search method"
    )
    beam_width: int = Field(3, ge=1, description="Beam width for beam search")
    confidence_threshold: float = Field(0.6, ge=0.0, le=1.0, description="Stop when confidence exceeds this")


class AgentConfig(BaseModel):
    """Optional agent for routing, reflection, or memory."""

    enabled: bool = Field(False, description="Enable agent step")
    agent_type: Literal["router", "reflection", "memory", "orchestrator"] = Field(
        "router", description="Agent type"
    )
    llm_model: str = Field("gpt-4o-mini", description="LLM for agent")

    # Router
    routing_mode: Literal["adaptive", "rule_based", "llm_classifier"] = Field(
        "adaptive", description="Query routing mode"
    )
    confidence_upper: float = Field(0.7, ge=0.0, le=1.0, description="Above = direct answer")
    confidence_lower: float = Field(0.3, ge=0.0, le=1.0, description="Below = web fallback")

    # Reflection
    max_retries: int = Field(3, ge=0, description="Max reflection retries")
    min_quality_score: float = Field(6.0, ge=0.0, le=10.0, description="Minimum quality score")

    # Memory
    max_history_turns: int = Field(20, ge=1, description="Conversation history to retain")
    summarization_enabled: bool = Field(True, description="Summarize long histories")


class QueryPipeline(BaseModel):
    id: str
    workspace_id: str = ""
    name: str
    description: str = ""
    datastore_id: str = Field(..., description="DataStore to query against")
    retrieval_strategy: str = Field(
        "auto", description="Retrieval strategy: auto | vector | graph | hybrid"
    )
    retriever: RetrieverConfig = Field(default_factory=RetrieverConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    generator: GeneratorConfig = Field(default_factory=GeneratorConfig)
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    definition: dict | None = Field(
        None, description="Visual pipeline definition (nodes/edges) from editor"
    )
    created_at: str = ""
    updated_at: str | None = None


def query_pipeline_to_tool(pipeline: QueryPipeline) -> dict:
    """Convert a QueryPipeline into an OpenAI function-calling tool schema."""
    return {
        "type": "function",
        "function": {
            "name": f"query_{pipeline.id.replace('-', '_')}",
            "description": (
                f"Search the '{pipeline.name}' knowledge base"
                + (f": {pipeline.description}" if pipeline.description else "")
                + f". Uses {pipeline.retrieval_strategy} retrieval strategy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information",
                    },
                },
                "required": ["query"],
            },
        },
    }


def tool_name_to_pipeline_id(tool_name: str) -> str:
    """Extract pipeline ID from tool function name."""
    prefix = "query_"
    if tool_name.startswith(prefix):
        return tool_name[len(prefix):].replace("_", "-")
    return tool_name
