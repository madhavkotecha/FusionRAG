# ADR-0012: YAML-First Pipeline Definition with Visual Sync

## Status

Accepted

## Implementation Status (as of 2026-05-12)

YAML pipeline definitions live in `rrag-ingestion/configs/pipelines/` — 6 shipping templates: `lightrag_default`, `corag_default`, `kag_default`, `quick_ingest`, `ultrarag_default`, `agentic_rag`. Each declares a sequence of `component:` blocks with parameters. The visual builder (ADR-0004, XYFlow-based) serializes graphs to the same component list — bi-directional sync is via the pipeline-service `templates.py` API (commit `b4a5575` "Parse template definitions and set pipeline_type").

## Context

The RAG IDE needs a canonical pipeline definition format. Options:
- JSON (XYFlow's native format) — tied to visual editor
- YAML — human-readable, version-controllable
- Code (Python DSL) — most flexible but highest barrier

The visual pipeline builder (XYFlow canvas) produces JSON. But pipelines need to be version-controlled, diffed in code review, shared as text, and edited without a GUI.

## Decision

**YAML is the canonical pipeline definition format.** The visual canvas is a synchronized view.

### Bidirectional Sync
- **Canvas → YAML**: On node/edge changes, compute diff, patch YAML
- **YAML → Canvas**: On text edits, parse, validate, apply diffs to canvas
- **Conflict resolution**: Last edit wins with 50ms debounce
- **Validation**: Both directions validate against component schemas before applying

### YAML Structure

```yaml
name: vanilla-rag
version: "1.0"
description: Basic retrieve-and-generate pipeline

steps:
  - id: reader
    component: reader.pdf
    config:
      extract_tables: true

  - id: chunker
    component: chunker.recursive
    config:
      chunk_size: 1200
      overlap: 100
    inputs:
      documents: reader.documents

  - id: embedder
    component: embedder.sentence_transformers
    config:
      model: all-MiniLM-L6-v2
    inputs:
      chunks: chunker.chunks

  - id: retriever
    component: retriever.dense_milvus
    config:
      top_k: 10
    inputs:
      query_embedding: embedder.embeddings

  - id: generator
    component: generator.vllm
    config:
      model: meta-llama/Llama-3.1-8B-Instruct
    inputs:
      context: retriever.results
```

### Control Flow Nodes
- **Loop**: Repeat steps N times with optional terminal condition
- **Branch**: Router evaluation → conditional path selection
- **Parallel**: Multiple branches simultaneously with merge strategy

### Two Pipeline Types
- **Ingestion pipelines**: Batch, offline, write-path (minutes-to-hours)
- **Query pipelines**: Real-time, per-query, read-path (sub-second-to-seconds)

## Consequences

**Positive:**
- Pipelines are version-controllable (git diff, code review)
- Human-readable without GUI
- Portable across environments (export YAML, import elsewhere)
- Bidirectional sync means both visual and text users are first-class
- YAML templates shareable as a gallery

**Negative:**
- Bidirectional sync adds implementation complexity (conflict resolution, debounce)
- YAML is less expressive than a Python DSL for complex logic
- Two representations (YAML + canvas state) must be kept in sync
- YAML editing requires schema knowledge (mitigated by Monaco autocompletion)

## Alternatives Considered

1. **JSON only (XYFlow native)**: Simpler sync — but poor readability, hard to diff
2. **Python DSL**: Most flexible — but requires Python knowledge, not GUI-editable
3. **Visual-only (no text format)**: Simplest UX — but no version control, no sharing, no automation
4. **Both YAML and JSON as first-class**: Flexible — but maintaining two parsers doubles complexity
