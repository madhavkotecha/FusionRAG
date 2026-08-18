import { useState, useMemo, useEffect, type DragEvent } from 'react';
import { ChevronDown, ChevronRight, GripVertical } from 'lucide-react';
import {
  Database, Scissors, Binary, Search, ArrowUpDown,
  Sparkles, FileSearch, Layers, HardDrive, Network, Bot, Brain,
  BookOpen, MessageSquare, GitBranch, Code2,
  type LucideIcon,
} from 'lucide-react';
import type { PipelineType, ComponentDefinition } from '../../types/pipeline';
import { pipelineApi } from '../../api/pipelines';
import { ComponentManager } from './ComponentManager';
import { useAuthStore } from '../../stores/auth.store';

const INGESTION_CATEGORIES = new Set([
  'parser', 'chunker', 'embedder', 'extractor', 'graph_builder', 'indexer', 'storage',
]);
const QUERY_CATEGORIES = new Set([
  'retriever', 'reranker', 'generator', 'planner', 'agent',
]);
const ALL_CATEGORIES = new Set([...INGESTION_CATEGORIES, ...QUERY_CATEGORIES]);

const CATEGORY_META: Record<string, { color: string; icon: LucideIcon }> = {
  parser: { color: 'text-slate-400 border-slate-500/30 bg-slate-500/5 hover:border-slate-400/50', icon: FileSearch },
  data_source: { color: 'text-blue-400 border-blue-500/30 bg-blue-500/5 hover:border-blue-400/50', icon: Database },
  chunker: { color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-400/50', icon: Scissors },
  extractor: { color: 'text-teal-400 border-teal-500/30 bg-teal-500/5 hover:border-teal-400/50', icon: Layers },
  embedder: { color: 'text-purple-400 border-purple-500/30 bg-purple-500/5 hover:border-purple-400/50', icon: Binary },
  indexer: { color: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/5 hover:border-indigo-400/50', icon: HardDrive },
  graph_builder: { color: 'text-pink-400 border-pink-500/30 bg-pink-500/5 hover:border-pink-400/50', icon: Network },
  storage: { color: 'text-stone-400 border-stone-500/30 bg-stone-500/5 hover:border-stone-400/50', icon: HardDrive },
  retriever: { color: 'text-orange-400 border-orange-500/30 bg-orange-500/5 hover:border-orange-400/50', icon: Search },
  reranker: { color: 'text-amber-400 border-amber-500/30 bg-amber-500/5 hover:border-amber-400/50', icon: ArrowUpDown },
  generator: { color: 'text-rose-400 border-rose-500/30 bg-rose-500/5 hover:border-rose-400/50', icon: Sparkles },
  planner: { color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/5 hover:border-cyan-400/50', icon: Brain },
  agent: { color: 'text-violet-400 border-violet-500/30 bg-violet-500/5 hover:border-violet-400/50', icon: Bot },
  knowledge_retrieval: { color: 'text-blue-400 border-blue-500/30 bg-blue-500/5 hover:border-blue-400/50', icon: BookOpen },
  llm: { color: 'text-fuchsia-400 border-fuchsia-500/30 bg-fuchsia-500/5 hover:border-fuchsia-400/50', icon: MessageSquare },
  control: { color: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/5 hover:border-yellow-400/50', icon: GitBranch },
  code: { color: 'text-zinc-400 border-zinc-500/30 bg-zinc-500/5 hover:border-zinc-400/50', icon: Code2 },
};

/** Hardcoded fallback — always available even when the API is unreachable. */
const DEFAULT_CATEGORIES = [
  {
    category: 'parser',
    label: 'Parsers',
    components: [
      { type: 'file_loader', label: 'File Loader' },
      { type: 'multi_parser', label: 'Multi-Format Parser' },
      { type: 'web_scraper', label: 'Web Scraper' },
    ],
  },
  {
    category: 'chunker',
    label: 'Chunkers',
    components: [
      { type: 'recursive_chunker', label: 'Recursive' },
      { type: 'semantic_chunker', label: 'Semantic' },
      { type: 'token_chunker', label: 'Token' },
      { type: 'sentence_chunker', label: 'Sentence' },
      { type: 'proposition_chunker', label: 'Proposition' },
      { type: 'contextual_chunker', label: 'Contextual' },
      { type: 'hierarchical_chunker', label: 'Hierarchical' },
      { type: 'document_structure_chunker', label: 'Doc Structure' },
    ],
  },
  {
    category: 'extractor',
    label: 'Extractors',
    components: [
      { type: 'schema_free_extractor', label: 'Schema-Free' },
      { type: 'schema_constrained_extractor', label: 'Schema-Constrained' },
      { type: 'entity_extractor', label: 'LightRAG Entity' },
      { type: 'subquery_decomposer', label: 'CoRAG Subquery' },
    ],
  },
  {
    category: 'embedder',
    label: 'Embedders',
    components: [
      { type: 'openai_embedder', label: 'OpenAI' },
      { type: 'sentence_transformer_embedder', label: 'Sentence Transformer' },
      { type: 'e5_embedder', label: 'E5' },
      { type: 'bge_m3_embedder', label: 'BGE-M3' },
      { type: 'cohere_embedder', label: 'Cohere' },
      { type: 'jina_embedder', label: 'Jina' },
      { type: 'nomic_embedder', label: 'Nomic' },
      { type: 'voyage_embedder', label: 'Voyage' },
      { type: 'multimodal_embedder', label: 'Multimodal (ColPali)' },
    ],
  },
  {
    category: 'indexer',
    label: 'Indexers',
    components: [
      { type: 'faiss_indexer', label: 'FAISS' },
      { type: 'milvus_indexer', label: 'Milvus' },
    ],
  },
  {
    category: 'graph_builder',
    label: 'Graph Builders',
    components: [
      { type: 'lightrag_graph_builder', label: 'LightRAG Graph' },
      { type: 'kag_subgraph_builder', label: 'KAG Subgraph' },
    ],
  },
  {
    category: 'storage',
    label: 'Storage',
    components: [
      { type: 'vector_store', label: 'Vector Store' },
      { type: 'graph_store', label: 'Graph Store' },
      { type: 'kv_store', label: 'KV Store' },
    ],
  },
  {
    category: 'retriever',
    label: 'Retrievers',
    components: [
      { type: 'dense_retriever', label: 'Dense' },
      { type: 'hybrid_retriever', label: 'Hybrid' },
      { type: 'graph_retriever', label: 'Graph' },
      { type: 'web_retriever', label: 'Web' },
      { type: 'streaming_retriever', label: 'Streaming (RAPID)' },
      { type: 'table_retriever', label: 'Table (TableRAG)' },
      { type: 'gfm_retriever', label: 'GFM Graph' },
    ],
  },
  {
    category: 'reranker',
    label: 'Rerankers',
    components: [
      { type: 'cross_encoder_reranker', label: 'Cross-Encoder' },
      { type: 'cohere_reranker', label: 'Cohere' },
      { type: 'jina_reranker', label: 'Jina' },
      { type: 'llm_listwise_reranker', label: 'LLM Listwise' },
      { type: 'context_compressor', label: 'Context Compressor' },
    ],
  },
  {
    category: 'generator',
    label: 'Generators',
    components: [
      { type: 'llm_generator', label: 'LLM Generator' },
      { type: 'speculative_generator', label: 'Speculative (Draft+Verify)' },
      { type: 'vision_generator', label: 'Vision (VisRAG)' },
    ],
  },
  {
    category: 'planner',
    label: 'Planners',
    components: [
      { type: 'corag_planner', label: 'CoRAG Strategy' },
      { type: 'mcts_planner', label: 'MCTS' },
      { type: 'kag_planner', label: 'KAG Planner' },
    ],
  },
  {
    category: 'agent',
    label: 'Agents',
    components: [
      { type: 'orchestrator_agent', label: 'Orchestrator' },
      { type: 'query_router', label: 'Router' },
      { type: 'reflection_agent', label: 'Reflection' },
      { type: 'memory_agent', label: 'Memory' },
      { type: 'tool_use_agent', label: 'Tool Use' },
      { type: 'self_cognition_gate', label: 'Self-Cognition Gate' },
      { type: 'deep_rag_agent', label: 'Deep RAG' },
      { type: 'adaptive_retrieval_controller', label: 'Adaptive Retrieval' },
      { type: 'rag_evaluator', label: 'RAG Evaluator' },
    ],
  },
  // Dify-inspired workflow nodes
  {
    category: 'knowledge_retrieval',
    label: 'Knowledge Store',
    components: [
      { type: 'knowledge_retrieval', label: 'Knowledge Store Retrieval' },
    ],
  },
  {
    category: 'llm',
    label: 'LLM',
    components: [
      { type: 'llm', label: 'LLM Node' },
    ],
  },
  {
    category: 'control',
    label: 'Control Flow',
    components: [
      { type: 'if_else', label: 'IF/ELSE' },
      { type: 'loop', label: 'Loop' },
      { type: 'human_input', label: 'Human Input' },
    ],
  },
  {
    category: 'code',
    label: 'Code & HTTP',
    components: [
      { type: 'code', label: 'Code (Python/JS)' },
      { type: 'http_request', label: 'HTTP Request' },
    ],
  },
];

type CategoryGroup = typeof DEFAULT_CATEGORIES[number];

/**
 * Merge API components into the default list additively:
 * - Any component type already in defaults keeps its label
 * - New types from the API are appended to their category
 * - New categories from the API are added at the end
 */
function mergeWithDefaults(
  apiComponents: { type: string; category: string; name: string }[],
): CategoryGroup[] {
  // Deep-clone defaults
  const merged: CategoryGroup[] = DEFAULT_CATEGORIES.map((c) => ({
    ...c,
    components: [...c.components],
  }));
  const catIndex = new Map<string, CategoryGroup>();
  for (const cat of merged) catIndex.set(cat.category, cat);

  // Track all known types per category
  const knownTypes = new Map<string, Set<string>>();
  for (const cat of merged) {
    knownTypes.set(cat.category, new Set(cat.components.map((c) => c.type)));
  }

  for (const comp of apiComponents) {
    const existing = knownTypes.get(comp.category);
    if (existing?.has(comp.type)) continue; // already present

    if (catIndex.has(comp.category)) {
      // Append new component to existing category
      const cat = catIndex.get(comp.category)!;
      cat.components.push({ type: comp.type, label: comp.name });
      existing!.add(comp.type);
    } else {
      // New category from API
      const newCat: CategoryGroup = {
        category: comp.category,
        label: comp.category.charAt(0).toUpperCase() + comp.category.slice(1).replace(/_/g, ' '),
        components: [{ type: comp.type, label: comp.name }],
      };
      merged.push(newCat);
      catIndex.set(comp.category, newCat);
      knownTypes.set(comp.category, new Set([comp.type]));
    }
  }

  return merged;
}

interface ComponentPaletteProps {
  pipelineType?: PipelineType;
}

export function ComponentPalette({ pipelineType }: ComponentPaletteProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [categories, setCategories] = useState<CategoryGroup[]>(DEFAULT_CATEGORIES);
  const [customComponents, setCustomComponents] = useState<ComponentDefinition[]>([]);
  const [allApiComponents, setAllApiComponents] = useState<ComponentDefinition[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const user = useAuthStore((s) => s.user);
  const workspaceId = user?.workspaces?.[0]?.workspaceId ?? 'default';

  // Try to fetch from API; on failure, keep defaults
  useEffect(() => {
    pipelineApi.getComponents().then(({ data }) => {
      if (data?.length) {
        setCategories(mergeWithDefaults(data));
        setAllApiComponents(data);
        setCustomComponents(data.filter((c: ComponentDefinition) => c.source === 'custom'));
      }
    }).catch(() => {
      // API unavailable — keep hardcoded defaults
    });
  }, [refreshKey]);

  const filteredCategories = useMemo(() => {
    // Always show all categories — the palette is a toolbox,
    // users may want cross-type components in advanced pipelines.
    // Group pipeline-type-relevant categories first for convenience.
    if (!pipelineType) return categories;
    const primary = pipelineType === 'ingestion' ? INGESTION_CATEGORIES : QUERY_CATEGORIES;
    const primaryCats = categories.filter((cat) => primary.has(cat.category));
    const secondaryCats = categories.filter(
      (cat) => !primary.has(cat.category) && ALL_CATEGORIES.has(cat.category),
    );
    const otherCats = categories.filter((cat) => !ALL_CATEGORIES.has(cat.category));
    return [...primaryCats, ...secondaryCats, ...otherCats];
  }, [pipelineType, categories]);

  const toggle = (cat: string) =>
    setCollapsed((prev) => ({ ...prev, [cat]: !prev[cat] }));

  // Build a lookup of composite component data from API
  const compositeInfo = useMemo(() => {
    const map = new Map<string, { steps: unknown[] }>();
    for (const comp of allApiComponents) {
      if (comp.isComposite && comp.steps) {
        map.set(comp.type, { steps: comp.steps });
      }
    }
    return map;
  }, [allApiComponents]);

  const onDragStart = (
    event: DragEvent,
    type: string,
    category: string,
    label: string
  ) => {
    const composite = compositeInfo.get(type);
    const payload: Record<string, unknown> = { type, category, label };
    if (composite) {
      payload.isComposite = true;
      payload.steps = composite.steps;
    }
    event.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify(payload)
    );
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="p-3 space-y-3 bg-surface-900">
      <h3 className="text-[10px] font-semibold text-text-muted uppercase tracking-widest px-1">
        Components
      </h3>
      {filteredCategories.map((cat) => {
        const meta = CATEGORY_META[cat.category];
        const Icon = meta?.icon || Layers;
        const isCollapsed = collapsed[cat.category];

        return (
          <div key={cat.category}>
            <button
              onClick={() => toggle(cat.category)}
              className="w-full flex items-center gap-2 px-1 py-1 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors"
            >
              {isCollapsed ? (
                <ChevronRight className="w-3 h-3 text-text-muted" />
              ) : (
                <ChevronDown className="w-3 h-3 text-text-muted" />
              )}
              <Icon className="w-3.5 h-3.5" />
              <span>{cat.label}</span>
              <span className="ml-auto text-[10px] text-text-muted">
                {cat.components.length}
              </span>
            </button>
            {!isCollapsed && (
              <div className="space-y-1 mt-1 ml-2">
                {cat.components.map((comp) => (
                  <div
                    key={comp.type}
                    draggable
                    onDragStart={(e) =>
                      onDragStart(e, comp.type, cat.category, comp.label)
                    }
                    className={`cursor-grab flex items-center gap-2 border rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all duration-150 active:scale-95 ${
                      meta?.color || 'text-text-secondary border-border-primary bg-surface-800'
                    }`}
                  >
                    <GripVertical className="w-3 h-3 opacity-40" />
                    {comp.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <ComponentManager
        workspaceId={workspaceId}
        customComponents={customComponents}
        onComponentRegistered={() => setRefreshKey((k) => k + 1)}
      />
    </div>
  );
}
