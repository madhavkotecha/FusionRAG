# ADR-0016: Component Registry with Factory Pattern and Lazy Loading

## Status

Accepted

## Implementation Status (as of 2026-05-12)

The `@register_component` decorator is the live registration mechanism — used by **all 30+ ingestion components** (chunkers, embedders, extractors, generators, graph builders, indexers, parsers, planners, retrievers, agents) and the composite-component framework in the pipeline service (ADR-0026, `framework/decorators.py`). Component discovery uses an AST-based scanner (`framework/scanner.py`) for static discovery and a MinIO-backed `ComponentLoader` (`framework/loader.py`) for user-uploaded components. Lazy import is the default; components import their heavy deps (sentence-transformers, qdrant-client, etc.) only when first instantiated.

## Context

The RAG IDE pipeline builder needs a system for managing dozens of component types across nine categories (readers, chunkers, extractors, embedders, retrievers, rerankers, generators, routers, evaluators). Components have varying resource requirements — some need GPU memory for model loading, others need database connections. Loading all components eagerly at startup would exhaust resources.

## Decision

### Component Registry
Central registry mapping `(category, type)` to component classes:

```python
@register_component("chunker", "recursive")
class RecursiveChunker(BaseComponent):
    ...
```

- **Auto-discovery**: Components self-register via decorator
- **Third-party support**: Entry points mechanism (like Haystack) for external plugins
- **Validation**: Registry validates component schemas at registration time

### BaseComponent Protocol
All components implement a common interface:

```python
class BaseComponent(ABC):
    def __init__(self, config: dict): ...      # Lightweight: store config only
    async def warm_up(self): ...               # Heavy: load models, connect stores
    async def execute(self, input: dict) -> dict: ...  # Run component logic
    async def close(self): ...                 # Release resources
```

### Lazy Model Loading
- `__init__()` stores configuration only — no GPU memory, no connections
- `warm_up()` called just before first execution — loads models, establishes connections
- `close()` releases GPU memory and connections when pipeline is done
- Prevents GPU exhaustion during pipeline design (where many components are instantiated but not executed)

### Pipeline Engine Lifecycle

| Phase | When | Resource Impact |
|-------|------|-----------------|
| **Parse** | Load YAML | Minimal |
| **Build** | Resolve DAG, instantiate components | Minimal (config only) |
| **Warm Up** | Before execution | High (models, connections) |
| **Execute** | Per query | Medium |
| **Close** | After execution | Frees resources |

### Component Categories

| Category | Types |
|----------|-------|
| Readers | PDF, DOCX, EPUB, Markdown, TXT, Web, MinerU |
| Chunkers | Token, Sentence, Recursive, Semantic, Table, ParentChild |
| Extractors | LightRAG, KAG Schema-Free, KAG Schema-Constrained, SpaCy |
| Embedders | SentenceTransformers, OpenAI, MiniCPM, Jina, Infinity |
| Retrievers | DenseFAISS, DenseMilvus, BM25, Hybrid, GraphTraversal, Web, KAG |
| Rerankers | CrossEncoder, Infinity, API, Cohere, PenaltyScoring |
| Generators | vLLM, OpenAI, Anthropic, HuggingFace, Multimodal |
| Routers | Complexity, PatternMatch, Threshold, LLMJudge |
| Evaluators | ExactMatch, F1, ROUGE, Trec, LLMJudge |

### Typed Connector Protocol
Every component declares input/output types. The canvas enforces connection compatibility at design time, preventing invalid pipeline configurations before execution.

## Consequences

**Positive:**
- Dozens of components manageable through single registry
- Lazy loading prevents resource exhaustion during design
- Self-registration eliminates manual registry maintenance
- Third-party plugins extend the system without core changes
- Typed connectors catch configuration errors at design time

**Negative:**
- Indirection (registry lookup vs. direct import) makes code navigation harder
- Lazy loading means first execution is slower (warm-up cost)
- Component interface is lowest-common-denominator — specialized components may feel constrained
- Registry validation adds startup time

## Alternatives Considered

1. **Direct imports (no registry)**: Simplest — but no auto-discovery, no plugin support, no lazy loading
2. **Service-based components (microservices)**: Most isolated — but massive overhead for simple operations
3. **Eager loading**: Simpler lifecycle — but GPU exhaustion risk during design
4. **Class hierarchy instead of protocol**: Stronger contracts — but less flexible for third-party components
