# ADR-0028: Knowledge Base as First-Class Domain Object

- **Status:** Accepted
- **Date:** 2026-04-21
- **Deciders:** Architecture Team
- **Relates to:** ADR-0003 (Multi-Tenant Workspace Data Model), ADR-0023 (Ingestion Persistence Migration), ADR-0029 (Published Query Endpoints)

## Context

Originally the ingestion service had two top-level entities: documents and pipelines. Documents floated free in a workspace; chunking/embedding/indexing config was duplicated per-pipeline or per-document. As users built multiple RAG flows over the same corpus (different chunking, different embeddings, different retrieval), there was no shared notion of "this set of documents, processed this way" — leading to duplicated state and ambiguous query targets.

A "knowledge base" (KB) is the standard industry abstraction for this: a named, workspace-scoped collection of documents with a fixed ingestion config and its own retrieval index.

## Decision

Introduce **`KnowledgeBase`** as a first-class persisted entity in the ingestion service. Each KB owns:

- Name, description, owning workspace
- Ingestion config: `chunk_strategy`, `chunk_size`, `chunk_overlap`, `embedding_provider`, `embedding_model`
- Retrieval config (free-form `dict` for retriever-specific params)
- A document list (KB-scoped, not workspace-global)

### API surface (`rrag-ingestion/src/rrag_ingestion/api/knowledge_bases.py`)

- `POST /api/v1/ingestion/knowledge-bases` — create
- `GET  /api/v1/ingestion/knowledge-bases?workspace_id=…` — list
- `GET  /api/v1/ingestion/knowledge-bases/{id}` — detail
- `PATCH /api/v1/ingestion/knowledge-bases/{id}` — update config
- `DELETE /api/v1/ingestion/knowledge-bases/{id}` — destroy (including indexes)
- `POST /api/v1/ingestion/knowledge-bases/{id}/documents` — upload doc to KB
- `GET  /api/v1/ingestion/knowledge-bases/{id}/documents` — list docs in KB

### Frontend

`rrag-frontend/src/pages/KnowledgeBasesPage.tsx` (list, create) and `KnowledgeBaseDetailPage.tsx` (per-KB documents, settings, status).

### Relationship to query pipelines

A query pipeline references a `datastore_id` (the KB) and pulls its retrieval config at execution time. Publishing (ADR-0029) requires a KB + query pipeline pair.

## Consequences

**Positive:**
- Clear ownership: changing the KB's chunking strategy triggers re-ingestion of all KB documents, not random pipelines
- Same documents can live in multiple KBs with different processing
- Published endpoints (ADR-0029) bind to a KB, giving callers a stable retrieval target
- UI affordance: users build mental models around KBs, not abstract pipelines

**Negative:**
- Re-ingestion is a "full rebuild" event when KB config changes (no incremental migration — ADR-0011 still deferred)
- Adds a level of indirection: documents are now KB-scoped, not workspace-flat. Older code that listed `/documents?workspace_id=` had to be updated.
- More aggressive cascade deletes — destroying a KB tears down chunks/vectors/graph entries it owned

## Alternatives Considered

1. **Stay document-flat** — simpler but pushes config duplication onto every pipeline.
2. **KB-as-tag** — a label on documents, not a separate entity. Loses ingestion-config ownership.
3. **Pipeline-owned datasets** — what we had implicitly. Pipelines became overloaded; same docs got re-processed for each pipeline.

## References

- Commits: `8e75e49` (KnowledgeBase APIs, Publish page, pipeline nodes), `8786ff7` (New DataStore wizard)
- Files: `rrag-ingestion/src/rrag_ingestion/api/knowledge_bases.py`, `rrag-frontend/src/pages/KnowledgeBasesPage.tsx`, `rrag-frontend/src/pages/KnowledgeBaseDetailPage.tsx`, `rrag-frontend/src/api/knowledge.ts`
