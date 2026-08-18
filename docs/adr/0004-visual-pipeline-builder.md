# ADR-0004: Visual Pipeline Builder with XYFlow

## Status

Accepted

## Context

Users need an intuitive way to compose RAG pipelines from reusable components (chunkers, embedders, retrievers, generators, rerankers). Options range from YAML/code-only configuration to full visual drag-and-drop editors.

## Decision

Implement a visual pipeline builder using:
- **XYFlow 12** (React Flow successor) for the drag-and-drop canvas
- **Monaco Editor** for inline configuration editing
- **Component Registry** pattern for extensible component types

Pipeline definitions are stored as JSON with `nodes` and `edges` arrays, matching XYFlow's native format. This makes the visual representation the source of truth.

## Consequences

**Positive:**
- Low barrier to entry for non-technical users
- Visual representation aids understanding of complex pipelines
- XYFlow is mature, well-maintained, and performant
- Monaco provides IDE-like editing for component configs
- JSON definition is portable and version-controllable

**Negative:**
- Complex UI to build and maintain
- XYFlow's data model may not perfectly map to execution semantics
- Visual editor limitations for very complex pipeline logic (loops, conditionals)

## Alternatives Considered

1. **YAML-only config**: Lower development cost but poor UX
2. **Custom canvas (Canvas API)**: Full control but massive development effort
3. **Blockly (Google)**: Block-based programming — too code-focused for this use case
