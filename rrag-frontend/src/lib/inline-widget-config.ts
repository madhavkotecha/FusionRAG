/**
 * Defines which config fields should be shown as inline widgets on each component's node face.
 * Maps componentType -> list of config keys to surface inline, with display metadata.
 */

export interface InlineWidgetDef {
  key: string;
  type: 'slider' | 'select' | 'toggle' | 'number';
  min?: number;
  max?: number;
  step?: number;
  options?: string[];  // for select
  label?: string;      // override key display
}

/** Default inline widgets per component type. Max 3 per node to keep them compact. */
export const INLINE_WIDGETS: Record<string, InlineWidgetDef[]> = {
  // Chunkers
  recursive_chunker:    [{ key: 'chunk_size', type: 'slider', min: 64, max: 4096, step: 64 }, { key: 'chunk_overlap', type: 'number', min: 0, max: 1024 }],
  semantic_chunker:     [{ key: 'max_chunk_size', type: 'slider', min: 100, max: 2000, step: 50 }],
  token_chunker:        [{ key: 'chunk_token_size', type: 'slider', min: 100, max: 4096, step: 100 }, { key: 'chunk_overlap_token_size', type: 'number', min: 0, max: 1024 }],
  contextual_chunker:   [{ key: 'chunk_size', type: 'slider', min: 64, max: 2048, step: 64 }, { key: 'context_model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o', 'claude-3-haiku'] }],
  proposition_chunker:  [{ key: 'proposition_model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o'] }, { key: 'decontextualize', type: 'toggle' }],

  // Embedders
  openai_embedder:      [{ key: 'provider', type: 'select', options: ['openai', 'ollama', 'vllm'] }, { key: 'model', type: 'select', options: ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'] }],

  // Retrievers
  dense_retriever:      [{ key: 'top_k', type: 'slider', min: 1, max: 100, step: 1 }],
  hybrid_retriever:     [{ key: 'top_k', type: 'slider', min: 1, max: 100, step: 1 }, { key: 'alpha', type: 'slider', min: 0, max: 1, step: 0.1 }],
  graph_retriever:      [{ key: 'top_k', type: 'slider', min: 1, max: 50, step: 1 }, { key: 'max_hops', type: 'number', min: 1, max: 10 }],
  web_retriever:        [{ key: 'max_results', type: 'number', min: 1, max: 20 }],
  streaming_retriever:  [{ key: 'top_k', type: 'slider', min: 1, max: 100, step: 1 }, { key: 'stream_batch_size', type: 'number', min: 1, max: 50 }],
  table_retriever:      [{ key: 'top_k', type: 'slider', min: 1, max: 50, step: 1 }, { key: 'cell_retrieval_enabled', type: 'toggle' }],

  // Rerankers
  cross_encoder_reranker: [{ key: 'top_k', type: 'slider', min: 1, max: 50, step: 1 }],
  rrf_fusion:           [{ key: 'k', type: 'number', min: 1, max: 200 }, { key: 'top_k', type: 'slider', min: 1, max: 50, step: 1 }],
  context_compressor:   [{ key: 'target_ratio', type: 'slider', min: 0.1, max: 1, step: 0.05, label: 'ratio' }, { key: 'query_focused', type: 'toggle' }],
  llm_listwise_reranker: [{ key: 'top_k', type: 'slider', min: 1, max: 50, step: 1 }],

  // Generators
  llm_generator:        [{ key: 'provider', type: 'select', options: ['openai', 'ollama', 'vllm'] }, { key: 'model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o', 'claude-3-haiku', 'claude-sonnet-4-20250514'] }, { key: 'temperature', type: 'slider', min: 0, max: 2, step: 0.1 }],
  speculative_generator: [{ key: 'draft_model', type: 'select', options: ['gpt-4o-mini', 'claude-3-haiku'] }, { key: 'num_drafts', type: 'number', min: 1, max: 5 }],
  vision_generator:     [{ key: 'model', type: 'select', options: ['gpt-4o', 'claude-sonnet-4-20250514'] }, { key: 'max_images', type: 'number', min: 1, max: 20 }],

  // Agents
  query_router:         [{ key: 'routing_mode', type: 'select', options: ['adaptive', 'rule_based', 'llm_classifier'] }],
  reflection_agent:     [{ key: 'min_quality_score', type: 'slider', min: 0, max: 10, step: 0.5, label: 'min score' }, { key: 'max_retries', type: 'number', min: 0, max: 10 }],
  memory_agent:         [{ key: 'max_history_turns', type: 'slider', min: 1, max: 50, step: 1, label: 'history' }, { key: 'summarization_enabled', type: 'toggle', label: 'summarize' }],
  self_cognition_gate:  [{ key: 'confidence_threshold', type: 'slider', min: 0, max: 1, step: 0.05, label: 'confidence' }],
  deep_rag_agent:       [{ key: 'max_reasoning_steps', type: 'slider', min: 1, max: 20, step: 1, label: 'max steps' }, { key: 'show_reasoning_trace', type: 'toggle', label: 'show trace' }],
  adaptive_retrieval_controller: [{ key: 'sufficiency_threshold', type: 'slider', min: 0, max: 1, step: 0.05, label: 'threshold' }, { key: 'max_retrieval_rounds', type: 'number', min: 1, max: 20 }],
  rag_evaluator:        [{ key: 'evaluation_mode', type: 'select', options: ['inline', 'post_hoc', 'continuous'] }, { key: 'trace_enabled', type: 'toggle', label: 'trace' }],
  orchestrator_agent:   [{ key: 'max_iterations', type: 'number', min: 1, max: 20 }],

  // Planners
  corag_planner:        [{ key: 'strategy', type: 'select', options: ['greedy', 'best_of_n', 'beam', 'tree_search'] }, { key: 'max_hops', type: 'number', min: 1, max: 10 }],
  mcts_planner:         [{ key: 'mcts_simulations', type: 'slider', min: 10, max: 500, step: 10, label: 'simulations' }, { key: 'max_depth', type: 'number', min: 1, max: 10 }],

  // Indexers
  faiss_indexer:        [{ key: 'index_path', type: 'select', options: ['./data/faiss_index', './data/custom_index'] }],
  bm25_indexer:         [{ key: 'k1', type: 'slider', min: 0, max: 3, step: 0.1 }, { key: 'b', type: 'slider', min: 0, max: 1, step: 0.05 }],

  // Dify-inspired nodes
  knowledge_retrieval:  [{ key: 'top_k', type: 'slider', min: 1, max: 50, step: 1 }, { key: 'search_method', type: 'select', options: ['semantic', 'keyword', 'hybrid'] }],
  llm:                  [{ key: 'provider', type: 'select', options: ['openai', 'ollama', 'vllm'] }, { key: 'model', type: 'select', options: ['gpt-4o-mini', 'gpt-4o', 'claude-sonnet-4-20250514', 'claude-3-haiku'] }, { key: 'temperature', type: 'slider', min: 0, max: 2, step: 0.1 }],
  if_else:              [],  // Conditions configured in PropertyInspector
  loop:                 [{ key: 'max_iterations', type: 'number', min: 1, max: 100, label: 'max iter' }],
  code:                 [{ key: 'language', type: 'select', options: ['python3', 'javascript'], label: 'lang' }],
  http_request:         [{ key: 'method', type: 'select', options: ['GET', 'POST', 'PUT', 'DELETE'] }],
  human_input:          [{ key: 'timeout_seconds', type: 'number', min: 60, max: 86400, label: 'timeout (s)' }],
};
