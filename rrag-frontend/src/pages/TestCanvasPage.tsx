/**
 * Standalone test page for the ComfyUI-style pipeline canvas.
 * Renders without auth so we can visually verify TypedNode, ContextMenu,
 * inline widgets, execution overlay, and the port system.
 * Route: /test-canvas
 */
import { useEffect, useState, useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { PipelineCanvas } from '../components/pipeline/PipelineCanvas';
import { ComponentPalette } from '../components/pipeline/ComponentPalette';
import { usePipelineEditorStore } from '../stores/pipeline-editor.store';
import type { NodeRunState } from '../hooks/usePipelineRunStream';
import { Play, Share2 } from 'lucide-react';
import { WorkflowShareDialog } from '../components/pipeline/WorkflowShareDialog';

const SAMPLE_NODES = [
  { id: 'n1', type: 'parser', position: { x: 50, y: 80 }, data: { label: 'File Loader', componentType: 'file_loader', category: 'parser', config: {} } },
  { id: 'n2', type: 'chunker', position: { x: 320, y: 80 }, data: { label: 'Recursive Chunker', componentType: 'recursive_chunker', category: 'chunker', config: { chunk_size: 512, chunk_overlap: 50 } } },
  { id: 'n3', type: 'embedder', position: { x: 590, y: 80 }, data: { label: 'OpenAI Embedder', componentType: 'openai_embedder', category: 'embedder', config: { model: 'text-embedding-3-small' } } },
  { id: 'n4', type: 'indexer', position: { x: 860, y: 80 }, data: { label: 'FAISS Indexer', componentType: 'faiss_indexer', category: 'indexer', config: {} } },
  { id: 'n5', type: 'retriever', position: { x: 50, y: 340 }, data: { label: 'Dense Retriever', componentType: 'dense_retriever', category: 'retriever', config: { top_k: 20 } } },
  { id: 'n6', type: 'reranker', position: { x: 320, y: 340 }, data: { label: 'Cross-Encoder Reranker', componentType: 'cross_encoder_reranker', category: 'reranker', config: { top_k: 5 } } },
  { id: 'n7', type: 'generator', position: { x: 590, y: 340 }, data: { label: 'LLM Generator', componentType: 'llm_generator', category: 'generator', config: { model: 'gpt-4o-mini', temperature: 0.7 } } },
  { id: 'n8', type: 'agent', position: { x: 860, y: 340 }, data: { label: 'Reflection Agent', componentType: 'reflection_agent', category: 'agent', config: { min_quality_score: 6, max_retries: 3 } } },
  { id: 'n9', type: 'agent', position: { x: 50, y: 600 }, data: { label: 'Self-Cognition Gate', componentType: 'self_cognition_gate', category: 'agent', config: { confidence_threshold: 0.7 } } },
  { id: 'n10', type: 'agent', position: { x: 320, y: 600 }, data: { label: 'RAG Evaluator', componentType: 'rag_evaluator', category: 'agent', config: { evaluation_mode: 'post_hoc', trace_enabled: true } } },
  { id: 'n11', type: 'planner', position: { x: 590, y: 600 }, data: { label: 'MCTS Planner', componentType: 'mcts_planner', category: 'planner', config: { mcts_simulations: 100, max_depth: 5 } } },
  { id: 'n12', type: 'agent', position: { x: 860, y: 600 }, data: { label: 'Memory Agent', componentType: 'memory_agent', category: 'agent', config: { max_history_turns: 20, summarization_enabled: true } } },
  // Dify-inspired nodes
  { id: 'n13', type: 'knowledge_retrieval', position: { x: 50, y: 860 }, data: { label: 'Knowledge Store Retrieval', componentType: 'knowledge_retrieval', category: 'knowledge_retrieval', config: { top_k: 20, search_method: 'hybrid' } } },
  { id: 'n14', type: 'llm', position: { x: 320, y: 860 }, data: { label: 'LLM Node', componentType: 'llm', category: 'llm', config: { model: 'gpt-4o-mini', temperature: 0.7 } } },
  { id: 'n15', type: 'if_else', position: { x: 590, y: 860 }, data: { label: 'Quality Check', componentType: 'if_else', category: 'if_else', config: {} } },
  { id: 'n16', type: 'code', position: { x: 860, y: 860 }, data: { label: 'Transform', componentType: 'code', category: 'code', config: { language: 'python3' } } },
];

const SAMPLE_EDGES = [
  { id: 'e1', source: 'n1', target: 'n2', sourceHandle: 'out-documents', targetHandle: 'in-documents', style: { stroke: '#3b82f6', strokeWidth: 2 } },
  { id: 'e2', source: 'n2', target: 'n3', sourceHandle: 'out-chunks', targetHandle: 'in-chunks', style: { stroke: '#8b5cf6', strokeWidth: 2 } },
  { id: 'e3', source: 'n3', target: 'n4', sourceHandle: 'out-embeddings', targetHandle: 'in-embeddings', style: { stroke: '#ec4899', strokeWidth: 2 } },
  { id: 'e4', source: 'n5', target: 'n6', sourceHandle: 'out-context', targetHandle: 'in-context', style: { stroke: '#84cc16', strokeWidth: 2 } },
  { id: 'e5', source: 'n6', target: 'n7', sourceHandle: 'out-context', targetHandle: 'in-context', style: { stroke: '#84cc16', strokeWidth: 2 } },
  // Loop edge: reflection agent retries back to retriever
  { id: 'e-loop', source: 'n8', target: 'n5', sourceHandle: 'out-retry', targetHandle: 'in-query', type: 'loop', data: { maxIterations: 3 } },
  // Dify-inspired workflow edges
  { id: 'e6', source: 'n13', target: 'n14', sourceHandle: 'out-context', targetHandle: 'in-context', style: { stroke: '#84cc16', strokeWidth: 2 } },
  { id: 'e7', source: 'n14', target: 'n15', sourceHandle: 'out-answer', targetHandle: 'in-input', style: { stroke: '#f97316', strokeWidth: 2 } },
];

const EXEC_ORDER = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'n8'];

export function TestCanvasPage() {
  const loadPipeline = usePipelineEditorStore((s) => s.loadPipeline);
  const [execStates, setExecStates] = useState<Map<string, NodeRunState>>(new Map());
  const [simRunning, setSimRunning] = useState(false);
  const [showShare, setShowShare] = useState(false);

  useEffect(() => {
    loadPipeline(SAMPLE_NODES as any, SAMPLE_EDGES as any);
  }, [loadPipeline]);

  /** Simulate a pipeline execution with per-node progress */
  const simulateExecution = useCallback(() => {
    if (simRunning) return;
    setSimRunning(true);
    setExecStates(new Map());

    // Set all nodes to pending
    const initial = new Map<string, NodeRunState>();
    for (const nodeId of EXEC_ORDER) {
      initial.set(nodeId, { nodeId, componentType: '', isComposite: false, status: 'pending', steps: [] });
    }
    setExecStates(new Map(initial));

    let step = 0;
    const interval = setInterval(() => {
      if (step >= EXEC_ORDER.length) {
        clearInterval(interval);
        setSimRunning(false);
        return;
      }
      const nodeId = EXEC_ORDER[step];
      // Set current to running
      setExecStates(prev => {
        const next = new Map(prev);
        const s = next.get(nodeId);
        if (s) next.set(nodeId, { ...s, status: 'running' });
        return next;
      });

      // After a delay, mark as completed
      const delay = 400 + Math.random() * 600;
      setTimeout(() => {
        setExecStates(prev => {
          const next = new Map(prev);
          const s = next.get(nodeId);
          if (s) next.set(nodeId, { ...s, status: 'completed', durationMs: Math.round(delay) });
          return next;
        });
      }, delay);

      step++;
    }, 700);

    return () => clearInterval(interval);
  }, [simRunning]);

  return (
    <div className="h-screen w-screen flex bg-surface-950 text-text-primary">
      {/* Left sidebar */}
      <div className="w-56 shrink-0 overflow-y-auto border-r border-border-primary">
        <ComponentPalette />
      </div>

      {/* Canvas area */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="h-10 shrink-0 flex items-center gap-3 px-4 border-b border-border-primary bg-surface-900">
          <span className="text-xs font-semibold text-text-primary">Test Canvas</span>
          <div className="flex-1" />
          <button
            onClick={() => setShowShare(true)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface-700 hover:bg-surface-600 text-text-primary text-xs font-medium transition-colors"
          >
            <Share2 className="w-3 h-3" />Share
          </button>
          <button
            onClick={simulateExecution}
            disabled={simRunning}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-accent-500 hover:bg-accent-600 disabled:opacity-50 text-white text-xs font-medium transition-colors"
          >
            <Play className="w-3 h-3" />
            {simRunning ? 'Running...' : 'Simulate Run'}
          </button>
        </div>
        <div className="flex-1">
          <ReactFlowProvider>
            <PipelineCanvas nodeExecutionStates={execStates} />
          </ReactFlowProvider>
        </div>
      </div>
      {showShare && <WorkflowShareDialog onClose={() => setShowShare(false)} />}
    </div>
  );
}
