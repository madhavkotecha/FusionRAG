import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { PipelineNodeData } from '../../../types/pipeline';
import {
  Database,
  Scissors,
  Binary,
  Search,
  ArrowUpDown,
  Sparkles,
  FileSearch,
  Layers,
  HardDrive,
  Bot,
  Brain,
  Network,
  type LucideIcon,
} from 'lucide-react';

interface CategoryMeta {
  gradient: string;
  handleColor: string;
  label: string;
  icon: LucideIcon;
}

const CATEGORIES: Record<string, CategoryMeta> = {
  data_source: { gradient: 'from-blue-600 to-blue-400', handleColor: '#3b82f6', label: 'Data Source', icon: Database },
  chunker: { gradient: 'from-emerald-600 to-emerald-400', handleColor: '#10b981', label: 'Chunker', icon: Scissors },
  embedder: { gradient: 'from-purple-600 to-purple-400', handleColor: '#a855f7', label: 'Embedder', icon: Binary },
  retriever: { gradient: 'from-orange-600 to-orange-400', handleColor: '#f97316', label: 'Retriever', icon: Search },
  reranker: { gradient: 'from-amber-600 to-amber-400', handleColor: '#f59e0b', label: 'Reranker', icon: ArrowUpDown },
  generator: { gradient: 'from-rose-600 to-rose-400', handleColor: '#f43f5e', label: 'Generator', icon: Sparkles },
  parser: { gradient: 'from-slate-600 to-slate-400', handleColor: '#64748b', label: 'Parser', icon: FileSearch },
  extractor: { gradient: 'from-teal-600 to-teal-400', handleColor: '#14b8a6', label: 'Extractor', icon: Layers },
  indexer: { gradient: 'from-indigo-600 to-indigo-400', handleColor: '#6366f1', label: 'Indexer', icon: HardDrive },
  graph_builder: { gradient: 'from-pink-600 to-pink-400', handleColor: '#ec4899', label: 'Graph Builder', icon: Network },
  storage: { gradient: 'from-stone-600 to-stone-400', handleColor: '#78716c', label: 'Storage', icon: HardDrive },
  agent: { gradient: 'from-violet-600 to-violet-400', handleColor: '#8b5cf6', label: 'Agent', icon: Bot },
  planner: { gradient: 'from-cyan-600 to-cyan-400', handleColor: '#06b6d4', label: 'Planner', icon: Brain },
};

const DEFAULT_META: CategoryMeta = {
  gradient: 'from-gray-600 to-gray-400',
  handleColor: '#6b7280',
  label: 'Component',
  icon: Layers,
};

export function BaseNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as PipelineNodeData;
  const meta = CATEGORIES[nodeData.category] || DEFAULT_META;
  const Icon = meta.icon;

  return (
    <div
      className={`rounded-xl min-w-[200px] transition-all duration-200 ${
        selected
          ? 'ring-2 ring-accent-500 shadow-lg shadow-accent-500/20'
          : 'ring-1 ring-border-primary shadow-lg shadow-black/30'
      } bg-surface-800`}
    >
      {/* Gradient header */}
      <div
        className={`bg-gradient-to-r ${meta.gradient} px-3 py-2 rounded-t-xl flex items-center gap-2`}
      >
        <Icon className="w-3.5 h-3.5 text-white/90" />
        <span className="text-xs font-semibold text-white/90 tracking-wide">
          {meta.label}
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5">
        <div className="text-sm font-medium text-text-primary">{nodeData.label}</div>
      </div>

      {/* Handles */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: meta.handleColor, border: '2px solid var(--color-surface-800)' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: meta.handleColor, border: '2px solid var(--color-surface-800)' }}
      />
    </div>
  );
}
