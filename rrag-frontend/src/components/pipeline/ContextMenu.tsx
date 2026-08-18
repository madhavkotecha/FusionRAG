import { useState, useRef, useEffect, useMemo } from 'react';
import { Search as SearchIcon, Plug } from 'lucide-react';
import {
  Database, Scissors, Binary, Search, ArrowUpDown,
  Sparkles, FileSearch, Layers, HardDrive, Network, Bot, Brain,
  BookOpen, MessageSquare, GitBranch, Repeat, Code2, Globe, UserCheck,
  type LucideIcon,
} from 'lucide-react';
import { getComponentPorts, isConnectionValid, PORT_COLORS, PORT_LABELS } from '../../lib/port-types';

export interface ContextMenuState {
  x: number;
  y: number;
  canvasX: number;
  canvasY: number;
  /** When set, only show components whose inputs are compatible with this port type */
  compatibleWithOutputType?: import('../../lib/port-types').PortType;
}

interface ContextMenuProps {
  state: ContextMenuState;
  onSelect: (type: string, category: string, label: string) => void;
  onClose: () => void;
}

interface ComponentItem {
  type: string;
  label: string;
  category: string;
  categoryLabel: string;
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  parser: FileSearch, chunker: Scissors, embedder: Binary,
  extractor: Layers, graph_builder: Network, indexer: HardDrive,
  storage: HardDrive, retriever: Search, reranker: ArrowUpDown,
  generator: Sparkles, planner: Brain, agent: Bot, data_source: Database,
  knowledge_retrieval: BookOpen, llm: MessageSquare,
  if_else: GitBranch, loop_node: Repeat, code: Code2,
  http_request: Globe, human_input: UserCheck,
};

const ALL_COMPONENTS: ComponentItem[] = [
  // Parsers
  { type: 'file_loader', label: 'File Loader', category: 'parser', categoryLabel: 'Parser' },
  { type: 'multi_parser', label: 'Multi-Format Parser', category: 'parser', categoryLabel: 'Parser' },
  { type: 'web_scraper', label: 'Web Scraper', category: 'parser', categoryLabel: 'Parser' },
  // Chunkers
  { type: 'recursive_chunker', label: 'Recursive Chunker', category: 'chunker', categoryLabel: 'Chunker' },
  { type: 'semantic_chunker', label: 'Semantic Chunker', category: 'chunker', categoryLabel: 'Chunker' },
  { type: 'token_chunker', label: 'Token Chunker', category: 'chunker', categoryLabel: 'Chunker' },
  { type: 'proposition_chunker', label: 'Proposition Chunker', category: 'chunker', categoryLabel: 'Chunker' },
  { type: 'contextual_chunker', label: 'Contextual Chunker', category: 'chunker', categoryLabel: 'Chunker' },
  // Embedders
  { type: 'openai_embedder', label: 'OpenAI Embedder', category: 'embedder', categoryLabel: 'Embedder' },
  { type: 'sentence_transformer_embedder', label: 'Sentence Transformer', category: 'embedder', categoryLabel: 'Embedder' },
  { type: 'multimodal_embedder', label: 'Multimodal (ColPali)', category: 'embedder', categoryLabel: 'Embedder' },
  // Extractors
  { type: 'entity_extractor', label: 'Entity Extractor', category: 'extractor', categoryLabel: 'Extractor' },
  { type: 'subquery_decomposer', label: 'Subquery Decomposer', category: 'extractor', categoryLabel: 'Extractor' },
  // Graph Builders
  { type: 'lightrag_graph_builder', label: 'LightRAG Graph Builder', category: 'graph_builder', categoryLabel: 'Graph Builder' },
  { type: 'kag_subgraph_builder', label: 'KAG Subgraph Builder', category: 'graph_builder', categoryLabel: 'Graph Builder' },
  // Indexers
  { type: 'faiss_indexer', label: 'FAISS Indexer', category: 'indexer', categoryLabel: 'Indexer' },
  { type: 'milvus_indexer', label: 'Milvus Indexer', category: 'indexer', categoryLabel: 'Indexer' },
  // Storage
  { type: 'graph_store', label: 'Graph Store (Neo4j)', category: 'storage', categoryLabel: 'Storage' },
  { type: 'vector_store', label: 'Vector Store', category: 'storage', categoryLabel: 'Storage' },
  { type: 'kv_store', label: 'Key-Value Store', category: 'storage', categoryLabel: 'Storage' },
  // Retrievers
  { type: 'dense_retriever', label: 'Dense Retriever', category: 'retriever', categoryLabel: 'Retriever' },
  { type: 'hybrid_retriever', label: 'Hybrid Retriever', category: 'retriever', categoryLabel: 'Retriever' },
  { type: 'graph_retriever', label: 'Graph Retriever', category: 'retriever', categoryLabel: 'Retriever' },
  { type: 'web_retriever', label: 'Web Retriever', category: 'retriever', categoryLabel: 'Retriever' },
  { type: 'streaming_retriever', label: 'Streaming Retriever', category: 'retriever', categoryLabel: 'Retriever' },
  { type: 'table_retriever', label: 'Table Retriever', category: 'retriever', categoryLabel: 'Retriever' },
  // Rerankers
  { type: 'cross_encoder_reranker', label: 'Cross-Encoder Reranker', category: 'reranker', categoryLabel: 'Reranker' },
  { type: 'rrf_fusion', label: 'RRF Fusion', category: 'reranker', categoryLabel: 'Reranker' },
  { type: 'context_compressor', label: 'Context Compressor', category: 'reranker', categoryLabel: 'Reranker' },
  { type: 'llm_listwise_reranker', label: 'LLM Listwise Reranker', category: 'reranker', categoryLabel: 'Reranker' },
  // Generators
  { type: 'llm_generator', label: 'LLM Generator', category: 'generator', categoryLabel: 'Generator' },
  { type: 'speculative_generator', label: 'Speculative Generator', category: 'generator', categoryLabel: 'Generator' },
  { type: 'vision_generator', label: 'Vision Generator', category: 'generator', categoryLabel: 'Generator' },
  // Planners
  { type: 'corag_planner', label: 'CoRAG Planner', category: 'planner', categoryLabel: 'Planner' },
  { type: 'mcts_planner', label: 'MCTS Planner', category: 'planner', categoryLabel: 'Planner' },
  { type: 'kag_planner', label: 'KAG Planner', category: 'planner', categoryLabel: 'Planner' },
  // Agents
  { type: 'query_router', label: 'Query Router', category: 'agent', categoryLabel: 'Agent' },
  { type: 'reflection_agent', label: 'Reflection Agent', category: 'agent', categoryLabel: 'Agent' },
  { type: 'memory_agent', label: 'Memory Agent', category: 'agent', categoryLabel: 'Agent' },
  { type: 'tool_use_agent', label: 'Tool Use Agent', category: 'agent', categoryLabel: 'Agent' },
  { type: 'orchestrator_agent', label: 'Orchestrator', category: 'agent', categoryLabel: 'Agent' },
  { type: 'self_cognition_gate', label: 'Self-Cognition Gate', category: 'agent', categoryLabel: 'Agent' },
  { type: 'deep_rag_agent', label: 'Deep RAG Agent', category: 'agent', categoryLabel: 'Agent' },
  { type: 'adaptive_retrieval_controller', label: 'Adaptive Retrieval', category: 'agent', categoryLabel: 'Agent' },
  { type: 'rag_evaluator', label: 'RAG Evaluator', category: 'agent', categoryLabel: 'Agent' },
  // Dify-inspired nodes
  { type: 'knowledge_retrieval', label: 'Knowledge Store Retrieval', category: 'knowledge_retrieval', categoryLabel: 'Knowledge Store' },
  { type: 'llm', label: 'LLM', category: 'llm', categoryLabel: 'LLM' },
  { type: 'if_else', label: 'IF/ELSE', category: 'if_else', categoryLabel: 'Control' },
  { type: 'loop', label: 'Loop', category: 'loop_node', categoryLabel: 'Control' },
  { type: 'code', label: 'Code', category: 'code', categoryLabel: 'Code' },
  { type: 'http_request', label: 'HTTP Request', category: 'http_request', categoryLabel: 'HTTP' },
  { type: 'human_input', label: 'Human Input', category: 'human_input', categoryLabel: 'Human' },
];

function fuzzyMatch(text: string, query: string): boolean {
  const lower = text.toLowerCase();
  const q = query.toLowerCase();
  let qi = 0;
  for (let i = 0; i < lower.length && qi < q.length; i++) {
    if (lower[i] === q[qi]) qi++;
  }
  return qi === q.length;
}

export function ContextMenu({ state, onSelect, onClose }: ContextMenuProps) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const filtered = useMemo(() => {
    let items = ALL_COMPONENTS;

    // Connection-aware filtering: only show components with compatible input ports
    if (state.compatibleWithOutputType) {
      const srcType = state.compatibleWithOutputType;
      items = items.filter(c => {
        const ports = getComponentPorts(c.type, c.category);
        return ports.inputs.some(p => isConnectionValid(srcType, p.type));
      });
    }

    if (!query.trim()) return items;
    return items.filter(
      c => fuzzyMatch(c.label, query) || fuzzyMatch(c.type, query) || fuzzyMatch(c.categoryLabel, query)
    );
  }, [query, state.compatibleWithOutputType]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault();
      const c = filtered[selectedIndex];
      onSelect(c.type, c.category, c.label);
    }
  };

  // Position: ensure menu stays within viewport
  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    left: Math.min(state.x, window.innerWidth - 280),
    top: Math.min(state.y, window.innerHeight - 400),
    zIndex: 9999,
  };

  return (
    <div ref={menuRef} style={menuStyle} className="w-64 bg-surface-800 border border-border-secondary rounded-xl shadow-2xl shadow-black/50 overflow-hidden animate-scale-in">
      {/* Search input */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border-primary">
        <SearchIcon className="w-3.5 h-3.5 text-text-muted shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search components..."
          className="w-full bg-transparent text-xs text-text-primary placeholder:text-text-muted outline-none"
        />
      </div>

      {/* Connection-aware hint */}
      {state.compatibleWithOutputType && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-900/80 border-b border-border-primary">
          <Plug className="w-3 h-3" style={{ color: PORT_COLORS[state.compatibleWithOutputType] }} />
          <span className="text-[9px] text-text-muted">
            Compatible with <span className="font-medium" style={{ color: PORT_COLORS[state.compatibleWithOutputType] }}>{PORT_LABELS[state.compatibleWithOutputType]}</span> output
          </span>
        </div>
      )}

      {/* Results */}
      <div className="max-h-[320px] overflow-y-auto py-1">
        {filtered.length === 0 && (
          <div className="px-3 py-4 text-xs text-text-muted text-center">No components found</div>
        )}
        {filtered.map((comp, i) => {
          const CatIcon = CATEGORY_ICONS[comp.category] || Layers;
          const isSelected = i === selectedIndex;
          return (
            <button
              key={comp.type}
              onClick={() => onSelect(comp.type, comp.category, comp.label)}
              onMouseEnter={() => setSelectedIndex(i)}
              className={`w-full flex items-center gap-2.5 px-3 py-1.5 text-left transition-colors ${
                isSelected ? 'bg-accent-500/15 text-text-primary' : 'text-text-secondary hover:bg-surface-700'
              }`}
            >
              <CatIcon className="w-3.5 h-3.5 shrink-0 opacity-60" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate">{comp.label}</div>
              </div>
              <span className="text-[9px] text-text-muted uppercase shrink-0">{comp.categoryLabel}</span>
            </button>
          );
        })}
      </div>

      <div className="px-3 py-1.5 border-t border-border-primary text-[9px] text-text-muted flex gap-3">
        <span><kbd className="px-1 py-0.5 rounded bg-surface-700 text-text-secondary">↑↓</kbd> navigate</span>
        <span><kbd className="px-1 py-0.5 rounded bg-surface-700 text-text-secondary">↵</kbd> select</span>
        <span><kbd className="px-1 py-0.5 rounded bg-surface-700 text-text-secondary">esc</kbd> close</span>
      </div>
    </div>
  );
}
