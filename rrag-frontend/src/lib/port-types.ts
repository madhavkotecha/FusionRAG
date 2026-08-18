/**
 * Port type system for the ComfyUI-style visual pipeline builder.
 * Defines the 13 semantic data types that flow between pipeline nodes.
 */

export const PORT_TYPES = [
  'document', 'chunk', 'embedding', 'entity', 'graph', 'index',
  'query', 'context', 'answer', 'signal', 'metadata', 'config', 'any',
] as const;

export type PortType = (typeof PORT_TYPES)[number];

/** Colors for port dots and edges, keyed by port type */
export const PORT_COLORS: Record<PortType, string> = {
  document:  '#3b82f6',  // blue-500
  chunk:     '#8b5cf6',  // violet-500
  embedding: '#ec4899',  // pink-500
  entity:    '#f59e0b',  // amber-500
  graph:     '#10b981',  // emerald-500
  index:     '#6366f1',  // indigo-500
  query:     '#06b6d4',  // cyan-500
  context:   '#84cc16',  // lime-500
  answer:    '#f97316',  // orange-500
  signal:    '#e11d48',  // rose-600
  metadata:  '#a855f7',  // purple-500
  config:    '#6b7280',  // gray-500
  any:       '#94a3b8',  // slate-400
};

/** Human-readable labels */
export const PORT_LABELS: Record<PortType, string> = {
  document:  'Document',
  chunk:     'Chunk',
  embedding: 'Embedding',
  entity:    'Entity',
  graph:     'Graph',
  index:     'Index',
  query:     'Query',
  context:   'Context',
  answer:    'Answer',
  signal:    'Signal',
  metadata:  'Metadata',
  config:    'Config',
  any:       'Any',
};

export interface PortDefinition {
  name: string;
  type: PortType;
  required?: boolean;
  multi?: boolean;
  description?: string;
  conditional_group?: string;
  condition_label?: string;
}

/** Compatibility matrix: source type -> which target types it can connect to */
const PORT_COMPATIBILITY: Record<PortType, readonly PortType[]> = {
  document:  ['document', 'any'],
  chunk:     ['chunk', 'any'],
  embedding: ['embedding', 'any'],
  entity:    ['entity', 'any'],
  graph:     ['graph', 'any'],
  index:     ['index', 'any'],
  query:     ['query', 'any'],
  context:   ['context', 'any'],
  answer:    ['answer', 'any'],
  signal:    ['signal', 'any'],
  metadata:  ['metadata', 'any'],
  config:    ['config', 'any'],
  any:       PORT_TYPES,
};

export function isConnectionValid(sourceType: PortType, targetType: PortType): boolean {
  return PORT_COMPATIBILITY[sourceType]?.includes(targetType) ?? false;
}

/**
 * Default port definitions for all component types.
 * Used when the backend doesn't provide typed ports.
 */
export const COMPONENT_PORTS: Record<string, { inputs: PortDefinition[]; outputs: PortDefinition[] }> = {
  // ── Parsers ───────────────────────────────────
  file_loader: {
    inputs: [],
    outputs: [{ name: 'documents', type: 'document' }],
  },
  multi_parser: {
    inputs: [{ name: 'files', type: 'document' }],
    outputs: [{ name: 'documents', type: 'document' }],
  },
  web_scraper: {
    inputs: [],
    outputs: [{ name: 'documents', type: 'document' }],
  },
  text_parser: {
    inputs: [],
    outputs: [{ name: 'documents', type: 'document' }],
  },
  table_parser: {
    inputs: [],
    outputs: [{ name: 'documents', type: 'document' }],
  },
  image_parser: {
    inputs: [],
    outputs: [{ name: 'documents', type: 'document' }],
  },

  // ── Chunkers ──────────────────────────────────
  recursive_chunker:        { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  semantic_chunker:         { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  token_chunker:            { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  sentence_chunker:         { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  proposition_chunker:      { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  contextual_chunker:       { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  hierarchical_chunker:     { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  document_structure_chunker: { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },
  row_chunker:              { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'chunks', type: 'chunk' }] },

  // ── Embedders ─────────────────────────────────
  openai_embedder:             { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  sentence_transformer_embedder: { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  e5_embedder:                 { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  bge_m3_embedder:             { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  cohere_embedder:             { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  jina_embedder:               { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  nomic_embedder:              { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  voyage_embedder:             { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  multimodal_embedder:         { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },
  clip_embedder:               { inputs: [{ name: 'documents', type: 'document' }], outputs: [{ name: 'embeddings', type: 'embedding' }] },

  // ── Extractors ────────────────────────────────
  schema_free_extractor:       { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'entities', type: 'entity' }] },
  schema_constrained_extractor: { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'entities', type: 'entity' }] },
  entity_extractor:            { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'entities', type: 'entity' }] },
  subquery_decomposer:         { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'queries', type: 'query' }] },

  // ── Graph Builders ────────────────────────────
  lightrag_graph_builder:      { inputs: [{ name: 'entities', type: 'entity' }], outputs: [{ name: 'graph', type: 'graph' }] },
  kag_subgraph_builder:        { inputs: [{ name: 'entities', type: 'entity' }], outputs: [{ name: 'graph', type: 'graph' }] },

  // ── Indexers ──────────────────────────────────
  faiss_indexer:               { inputs: [{ name: 'embeddings', type: 'embedding' }], outputs: [{ name: 'index', type: 'index' }] },
  milvus_indexer:              { inputs: [{ name: 'embeddings', type: 'embedding' }], outputs: [{ name: 'index', type: 'index' }] },
  bm25_indexer:                { inputs: [{ name: 'chunks', type: 'chunk' }], outputs: [{ name: 'index', type: 'index' }] },

  // ── Storage ───────────────────────────────────
  graph_store:  { inputs: [{ name: 'graph', type: 'graph' }], outputs: [{ name: 'stored', type: 'graph' }] },
  vector_store: { inputs: [{ name: 'embeddings', type: 'embedding' }], outputs: [{ name: 'stored', type: 'any' }] },
  kv_store:     { inputs: [{ name: 'data', type: 'any' }], outputs: [{ name: 'stored', type: 'any' }] },
  doc_store:    { inputs: [{ name: 'data', type: 'any' }], outputs: [{ name: 'stored', type: 'any' }] },

  // ── Retrievers ────────────────────────────────
  dense_retriever:     { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },
  hybrid_retriever:    { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },
  graph_retriever:     { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },
  web_retriever:       { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },
  streaming_retriever: { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },
  table_retriever:     { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },
  gfm_retriever:       { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'context', type: 'context' }] },

  // ── Rerankers ─────────────────────────────────
  cross_encoder_reranker: { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'context', type: 'context' }] },
  cohere_reranker:        { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'context', type: 'context' }] },
  jina_reranker:          { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'context', type: 'context' }] },
  llm_listwise_reranker:  { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'context', type: 'context' }] },
  rrf_fusion:             { inputs: [{ name: 'context', type: 'context', multi: true }], outputs: [{ name: 'context', type: 'context' }] },
  context_compressor:     { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'context', type: 'context' }] },

  // ── Generators ────────────────────────────────
  llm_generator:         { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'answer', type: 'answer' }] },
  speculative_generator: { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'answer', type: 'answer' }] },
  vision_generator:      { inputs: [{ name: 'query', type: 'query' }, { name: 'images', type: 'document' }], outputs: [{ name: 'answer', type: 'answer' }] },

  // ── Agents ────────────────────────────────────
  query_router: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'query', type: 'query' }, { name: 'routing', type: 'signal' }],
  },
  reflection_agent: {
    inputs: [
      { name: 'query', type: 'query', required: true },
      { name: 'answer', type: 'answer', required: true },
      { name: 'context', type: 'context', required: false },
    ],
    outputs: [
      { name: 'answer', type: 'answer', conditional_group: 'verdict', condition_label: 'Approved' },
      { name: 'retry', type: 'signal', conditional_group: 'verdict', condition_label: 'Retry' },
      { name: 'scores', type: 'metadata' },
    ],
  },
  memory_agent: {
    inputs:  [{ name: 'query', type: 'query', required: true }, { name: 'answer', type: 'answer', required: false }],
    outputs: [{ name: 'enriched_query', type: 'query' }],
  },
  tool_use_agent: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'tool_results', type: 'context' }, { name: 'trace', type: 'metadata' }],
  },
  orchestrator_agent: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'answer', type: 'answer' }, { name: 'trace', type: 'metadata' }],
  },
  self_cognition_gate: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [
      { name: 'query', type: 'query', conditional_group: 'decision', condition_label: 'Needs Retrieval' },
      { name: 'answer', type: 'answer', conditional_group: 'decision', condition_label: 'Confident' },
      { name: 'confidence', type: 'metadata' },
    ],
  },
  deep_rag_agent: {
    inputs:  [{ name: 'query', type: 'query', required: true }, { name: 'context', type: 'context', required: true }],
    outputs: [{ name: 'answer', type: 'answer' }, { name: 'trace', type: 'metadata' }],
  },
  adaptive_retrieval_controller: {
    inputs:  [{ name: 'query', type: 'query', required: true }, { name: 'context', type: 'context', required: true }],
    outputs: [
      { name: 'context', type: 'context', conditional_group: 'sufficiency', condition_label: 'Sufficient' },
      { name: 'need_more', type: 'signal', conditional_group: 'sufficiency', condition_label: 'Need More' },
    ],
  },
  rag_evaluator: {
    inputs: [
      { name: 'query', type: 'query', required: true },
      { name: 'context', type: 'context', required: true },
      { name: 'answer', type: 'answer', required: true },
    ],
    outputs: [
      { name: 'answer', type: 'answer' },
      { name: 'scores', type: 'metadata' },
      { name: 'trace', type: 'metadata' },
    ],
  },
  relevance_evaluator: {
    inputs:  [{ name: 'query', type: 'query', required: true }, { name: 'context', type: 'context', required: true }],
    outputs: [{ name: 'context', type: 'context' }, { name: 'scores', type: 'metadata' }],
  },
  self_critique_agent: {
    inputs:  [{ name: 'query', type: 'query', required: true }, { name: 'answer', type: 'answer', required: true }],
    outputs: [
      { name: 'answer', type: 'answer', conditional_group: 'verdict', condition_label: 'Approved' },
      { name: 'retry', type: 'signal', conditional_group: 'verdict', condition_label: 'Retry' },
    ],
  },
  citation_annotator: {
    inputs:  [{ name: 'answer', type: 'answer', required: true }],
    outputs: [{ name: 'answer', type: 'answer' }],
  },

  // ── Planners ──────────────────────────────────
  corag_planner: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'plan', type: 'signal' }],
  },
  mcts_planner: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'plan', type: 'signal' }],
  },
  kag_planner: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'plan', type: 'signal' }],
  },

  // ── Composite components ──────────────────────
  lightrag_ingestion: {
    inputs:  [{ name: 'documents', type: 'document' }],
    outputs: [{ name: 'stored', type: 'any' }],
  },
  lightrag_retrieval: {
    inputs:  [{ name: 'query', type: 'query' }],
    outputs: [{ name: 'answer', type: 'answer' }],
  },
  agentic_rag_retrieval: {
    inputs:  [{ name: 'query', type: 'query' }],
    outputs: [{ name: 'answer', type: 'answer' }],
  },

  // ── Dify-inspired nodes ───────────────────────
  knowledge_retrieval: {
    inputs:  [{ name: 'query', type: 'query', required: true }],
    outputs: [{ name: 'context', type: 'context' }],
  },
  llm: {
    inputs:  [{ name: 'query', type: 'query', required: true }, { name: 'context', type: 'context', required: false }],
    outputs: [{ name: 'answer', type: 'answer' }, { name: 'usage', type: 'metadata' }],
  },
  if_else: {
    inputs:  [{ name: 'input', type: 'any', required: true }],
    outputs: [
      { name: 'if', type: 'any', conditional_group: 'branch', condition_label: 'True' },
      { name: 'else', type: 'any', conditional_group: 'branch', condition_label: 'False' },
    ],
  },
  loop: {
    inputs:  [{ name: 'items', type: 'any', required: true }],
    outputs: [{ name: 'item', type: 'any' }, { name: 'results', type: 'any' }],
  },
  code: {
    inputs:  [{ name: 'input', type: 'any', required: true }],
    outputs: [{ name: 'output', type: 'any' }],
  },
  http_request: {
    inputs:  [{ name: 'input', type: 'any', required: false }],
    outputs: [{ name: 'response', type: 'any' }, { name: 'status', type: 'metadata' }],
  },
  human_input: {
    inputs:  [{ name: 'data', type: 'any', required: true }],
    outputs: [
      { name: 'approved', type: 'any', conditional_group: 'action', condition_label: 'Approved' },
      { name: 'rejected', type: 'signal', conditional_group: 'action', condition_label: 'Rejected' },
    ],
  },
};

/** Get port definitions for a component type, with fallback to generic single-port */
export function getComponentPorts(componentType: string, category?: string): { inputs: PortDefinition[]; outputs: PortDefinition[] } {
  if (COMPONENT_PORTS[componentType]) {
    return COMPONENT_PORTS[componentType];
  }
  // Fallback: derive from category
  return getFallbackPorts(category ?? 'unknown');
}

function getFallbackPorts(category: string): { inputs: PortDefinition[]; outputs: PortDefinition[] } {
  switch (category) {
    case 'parser':       return { inputs: [], outputs: [{ name: 'output', type: 'document' }] };
    case 'chunker':      return { inputs: [{ name: 'input', type: 'document' }], outputs: [{ name: 'output', type: 'chunk' }] };
    case 'embedder':     return { inputs: [{ name: 'input', type: 'chunk' }], outputs: [{ name: 'output', type: 'embedding' }] };
    case 'extractor':    return { inputs: [{ name: 'input', type: 'chunk' }], outputs: [{ name: 'output', type: 'entity' }] };
    case 'graph_builder': return { inputs: [{ name: 'input', type: 'entity' }], outputs: [{ name: 'output', type: 'graph' }] };
    case 'indexer':      return { inputs: [{ name: 'input', type: 'embedding' }], outputs: [{ name: 'output', type: 'index' }] };
    case 'storage':      return { inputs: [{ name: 'input', type: 'any' }], outputs: [{ name: 'output', type: 'any' }] };
    case 'retriever':    return { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'output', type: 'context' }] };
    case 'reranker':     return { inputs: [{ name: 'input', type: 'context' }], outputs: [{ name: 'output', type: 'context' }] };
    case 'generator':    return { inputs: [{ name: 'query', type: 'query' }, { name: 'context', type: 'context' }], outputs: [{ name: 'output', type: 'answer' }] };
    case 'agent':        return { inputs: [{ name: 'input', type: 'any' }], outputs: [{ name: 'output', type: 'any' }] };
    case 'planner':      return { inputs: [{ name: 'query', type: 'query' }], outputs: [{ name: 'plan', type: 'signal' }] };
    default:             return { inputs: [{ name: 'input', type: 'any' }], outputs: [{ name: 'output', type: 'any' }] };
  }
}
