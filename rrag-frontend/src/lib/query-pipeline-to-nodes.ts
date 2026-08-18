import type { Node, Edge } from '@xyflow/react';
import type { PipelineNodeData } from '../types/pipeline';
import type { QueryPipeline } from '../api/chat';

/** Strategy → component type mapping for retrievers */
const RETRIEVER_MAP: Record<string, { type: string; label: string }> = {
  dense: { type: 'dense_retriever', label: 'Dense Retriever' },
  hybrid: { type: 'hybrid_retriever', label: 'Hybrid Retriever' },
  graph: { type: 'graph_retriever', label: 'Graph Retriever' },
  web: { type: 'web_retriever', label: 'Web Retriever' },
  streaming: { type: 'streaming_retriever', label: 'Streaming Retriever' },
  table: { type: 'table_retriever', label: 'Table Retriever' },
};

/** Strategy → component type mapping for rerankers */
const RERANKER_MAP: Record<string, { type: string; label: string }> = {
  cross_encoder: { type: 'cross_encoder_reranker', label: 'Cross-Encoder Reranker' },
  cohere: { type: 'cohere_reranker', label: 'Cohere Reranker' },
  jina: { type: 'jina_reranker', label: 'Jina Reranker' },
  llm_listwise: { type: 'llm_listwise_reranker', label: 'LLM Listwise Reranker' },
  context_compressor: { type: 'context_compressor', label: 'Context Compressor' },
};

/** Strategy → component type mapping for planners */
const PLANNER_MAP: Record<string, { type: string; label: string }> = {
  corag: { type: 'corag_planner', label: 'CoRAG Planner' },
  mcts: { type: 'mcts_planner', label: 'MCTS Planner' },
  kag: { type: 'kag_planner', label: 'KAG Planner' },
};

/** Agent type → component type mapping */
const AGENT_MAP: Record<string, { type: string; label: string }> = {
  router: { type: 'query_router', label: 'Query Router' },
  reflection: { type: 'reflection_agent', label: 'Reflection Agent' },
  memory: { type: 'memory_agent', label: 'Memory Agent' },
  orchestrator: { type: 'orchestrator_agent', label: 'Orchestrator' },
  tool_use: { type: 'tool_use_agent', label: 'Tool Use Agent' },
};

const X_START = 100;
const Y_START = 80;
const Y_GAP = 160;

/**
 * Convert a QueryPipeline's structured config into visual nodes and edges
 * for the pipeline canvas, when no visual definition exists.
 */
export function queryPipelineToNodes(
  qp: QueryPipeline,
): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const nodes: Node<PipelineNodeData>[] = [];
  const edges: Edge[] = [];
  let y = Y_START;

  // 1. Retriever (always present)
  const retStrategy = qp.retriever?.strategy ?? 'dense';
  const retInfo = RETRIEVER_MAP[retStrategy] ?? { type: 'dense_retriever', label: 'Dense Retriever' };
  const retrieverId = crypto.randomUUID();
  nodes.push({
    id: retrieverId,
    type: 'retriever',
    position: { x: X_START, y },
    data: {
      label: retInfo.label,
      componentType: retInfo.type,
      category: 'retriever',
      config: { ...qp.retriever },
    },
  });
  let lastNodeId = retrieverId;
  y += Y_GAP;

  // 2. Reranker (if enabled)
  if (qp.reranker?.enabled) {
    const rrStrategy = qp.reranker.strategy ?? 'cross_encoder';
    const rrInfo = RERANKER_MAP[rrStrategy] ?? { type: 'cross_encoder_reranker', label: 'Cross-Encoder Reranker' };
    const rerankerId = crypto.randomUUID();
    nodes.push({
      id: rerankerId,
      type: 'reranker',
      position: { x: X_START, y },
      data: {
        label: rrInfo.label,
        componentType: rrInfo.type,
        category: 'reranker',
        config: { ...qp.reranker },
      },
    });
    edges.push({
      id: `e-${lastNodeId}-${rerankerId}`,
      source: lastNodeId,
      target: rerankerId,
    });
    lastNodeId = rerankerId;
    y += Y_GAP;
  }

  // 3. Planner (if enabled)
  if (qp.planner?.enabled) {
    const plStrategy = qp.planner.strategy ?? 'corag';
    const plInfo = PLANNER_MAP[plStrategy] ?? { type: 'corag_planner', label: 'CoRAG Planner' };
    const plannerId = crypto.randomUUID();
    nodes.push({
      id: plannerId,
      type: 'planner',
      position: { x: X_START, y },
      data: {
        label: plInfo.label,
        componentType: plInfo.type,
        category: 'planner',
        config: { ...qp.planner },
      },
    });
    edges.push({
      id: `e-${lastNodeId}-${plannerId}`,
      source: lastNodeId,
      target: plannerId,
    });
    lastNodeId = plannerId;
    y += Y_GAP;
  }

  // 4. Generator (always present)
  const generatorId = crypto.randomUUID();
  nodes.push({
    id: generatorId,
    type: 'generator',
    position: { x: X_START, y },
    data: {
      label: 'LLM Generator',
      componentType: 'llm_generator',
      category: 'generator',
      config: { ...qp.generator },
    },
  });
  edges.push({
    id: `e-${lastNodeId}-${generatorId}`,
    source: lastNodeId,
    target: generatorId,
  });
  lastNodeId = generatorId;
  y += Y_GAP;

  // 5. Agent (if enabled)
  if (qp.agent?.enabled) {
    const agType = qp.agent.agent_type ?? 'router';
    const agInfo = AGENT_MAP[agType] ?? { type: 'query_router', label: 'Query Router' };
    const agentId = crypto.randomUUID();
    nodes.push({
      id: agentId,
      type: 'agent',
      position: { x: X_START, y },
      data: {
        label: agInfo.label,
        componentType: agInfo.type,
        category: 'agent',
        config: { ...qp.agent },
      },
    });
    edges.push({
      id: `e-${lastNodeId}-${agentId}`,
      source: lastNodeId,
      target: agentId,
    });
    y += Y_GAP;
  }

  return { nodes, edges };
}
