import { Handle, Position, type NodeProps } from '@xyflow/react';
import { memo, useMemo, useCallback } from 'react';
import type { PipelineNodeData } from '../../../types/pipeline';
import { getComponentPorts, PORT_COLORS, PORT_LABELS, type PortDefinition } from '../../../lib/port-types';
import { INLINE_WIDGETS, type InlineWidgetDef } from '../../../lib/inline-widget-config';
import { usePipelineEditorStore } from '../../../stores/pipeline-editor.store';
import {
  Database, Scissors, Binary, Search, ArrowUpDown,
  Sparkles, FileSearch, Layers, HardDrive, Bot, Brain, Network, Zap,
  CheckCircle, XCircle, Loader2,
  BookOpen, MessageSquare, GitBranch, Repeat, Code2, Globe, UserCheck,
  type LucideIcon,
} from 'lucide-react';

/* ── Category Styling ─────────────────────────── */
/* Flat accent colors (Langflow-style) instead of gradients */

interface CategoryMeta {
  bg: string;         // Header background
  accent: string;     // Accent color for borders
  label: string;
  icon: LucideIcon;
}

const CATEGORIES: Record<string, CategoryMeta> = {
  data_source:   { bg: 'bg-blue-600', accent: '#3b82f6', label: 'Source', icon: Database },
  chunker:       { bg: 'bg-emerald-600', accent: '#10b981', label: 'Chunker', icon: Scissors },
  embedder:      { bg: 'bg-purple-600', accent: '#a855f7', label: 'Embedder', icon: Binary },
  retriever:     { bg: 'bg-orange-600', accent: '#f97316', label: 'Retriever', icon: Search },
  reranker:      { bg: 'bg-amber-600', accent: '#f59e0b', label: 'Reranker', icon: ArrowUpDown },
  generator:     { bg: 'bg-rose-600', accent: '#f43f5e', label: 'Generator', icon: Sparkles },
  parser:        { bg: 'bg-slate-600', accent: '#64748b', label: 'Parser', icon: FileSearch },
  extractor:     { bg: 'bg-teal-600', accent: '#14b8a6', label: 'Extractor', icon: Layers },
  indexer:       { bg: 'bg-indigo-600', accent: '#6366f1', label: 'Indexer', icon: HardDrive },
  graph_builder: { bg: 'bg-pink-600', accent: '#ec4899', label: 'Graph', icon: Network },
  storage:       { bg: 'bg-stone-600', accent: '#78716c', label: 'Storage', icon: HardDrive },
  agent:         { bg: 'bg-violet-600', accent: '#8b5cf6', label: 'Agent', icon: Bot },
  planner:       { bg: 'bg-cyan-600', accent: '#06b6d4', label: 'Planner', icon: Brain },
  knowledge_retrieval: { bg: 'bg-indigo-600', accent: '#4f46e5', label: 'Knowledge Store', icon: BookOpen },
  llm:           { bg: 'bg-fuchsia-600', accent: '#d946ef', label: 'LLM', icon: MessageSquare },
  control:       { bg: 'bg-yellow-600', accent: '#eab308', label: 'Control', icon: GitBranch },
  if_else:       { bg: 'bg-amber-600', accent: '#f59e0b', label: 'IF/ELSE', icon: GitBranch },
  loop_node:     { bg: 'bg-sky-600', accent: '#0ea5e9', label: 'Loop', icon: Repeat },
  code:          { bg: 'bg-zinc-600', accent: '#71717a', label: 'Code', icon: Code2 },
  http_request:  { bg: 'bg-green-600', accent: '#22c55e', label: 'HTTP', icon: Globe },
  human_input:   { bg: 'bg-lime-600', accent: '#84cc16', label: 'Human', icon: UserCheck },
};

const DEFAULT_META: CategoryMeta = { bg: 'bg-gray-600', accent: '#6b7280', label: 'Node', icon: Layers };

/* ── Layout Constants ─────────────────────────── */

const NODE_WIDTH = 280;           // Fixed width like Dify's 240px but wider for our ports
const HEADER_HEIGHT = 40;         // Taller header for readability
const PORT_ROW_HEIGHT = 28;       // More breathing room
const PORT_SECTION_PAD = 10;
const WIDGET_ROW_HEIGHT = 30;     // Taller for usable sliders
const BOTTOM_PADDING = 8;

/* ── Port Dot ─────────────────────────────────── */

function PortDot({ port, side }: { port: PortDefinition; side: 'left' | 'right' }) {
  const color = PORT_COLORS[port.type] || PORT_COLORS.any;
  const isSignal = port.type === 'signal';
  const isMetadata = port.type === 'metadata';
  const isOptional = port.required === false;

  return (
    <div
      className={`flex items-center gap-2 ${side === 'right' ? 'flex-row-reverse' : ''}`}
      title={`${port.name} (${PORT_LABELS[port.type]})${port.description ? ` — ${port.description}` : ''}${port.condition_label ? ` [${port.condition_label}]` : ''}`}
    >
      <div className="flex items-center justify-center" style={{ width: 14, height: 14 }}>
        {isSignal ? (
          <Zap className="w-3 h-3" style={{ color }} />
        ) : (
          <div
            className="rounded-full transition-transform hover:scale-125"
            style={{
              width: isMetadata ? 7 : 9,
              height: isMetadata ? 7 : 9,
              backgroundColor: isOptional ? 'transparent' : color,
              border: `2px solid ${color}`,
              ...(port.multi ? { boxShadow: `0 0 0 2px var(--color-surface-800), 0 0 0 4px ${color}` } : {}),
            }}
          />
        )}
      </div>
      <span
        className={`text-[10px] leading-tight ${isMetadata ? 'text-text-muted' : 'text-text-secondary'}`}
        style={{ maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
      >
        {port.name.replace(/_/g, ' ')}
        {port.condition_label && (
          <span className="text-text-muted/70 ml-1 text-[9px]">({port.condition_label})</span>
        )}
      </span>
    </div>
  );
}

/* ── Inline Widgets (with nodrag class to fix slider interaction) ── */

/** Wrapper that prevents React Flow from capturing pointer events */
function WidgetWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="nodrag nopan flex items-center gap-2 w-full"
      onPointerDownCapture={e => e.stopPropagation()}
      onMouseDownCapture={e => e.stopPropagation()}
    >
      {children}
    </div>
  );
}

function InlineSlider({ def, value, onChange }: { def: InlineWidgetDef; value: number; onChange: (v: number) => void }) {
  const min = def.min ?? 0;
  const max = def.max ?? 100;
  return (
    <WidgetWrapper>
      <span className="text-[10px] text-text-muted w-16 shrink-0 truncate">{def.label || def.key.replace(/_/g, ' ')}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={def.step ?? 1}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="nodrag nopan flex-1 h-1.5 rounded-full cursor-pointer accent-accent-500 appearance-none"
        style={{ background: `linear-gradient(to right, var(--color-accent-500) ${((value - min) / (max - min)) * 100}%, var(--color-surface-600) ${((value - min) / (max - min)) * 100}%)` }}
      />
      <span className="text-[10px] text-text-secondary w-8 text-right tabular-nums shrink-0">{value}</span>
    </WidgetWrapper>
  );
}

function InlineSelect({ def, value, onChange }: { def: InlineWidgetDef; value: string; onChange: (v: string) => void }) {
  return (
    <WidgetWrapper>
      <span className="text-[10px] text-text-muted w-16 shrink-0 truncate">{def.label || def.key.replace(/_/g, ' ')}</span>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="nodrag nopan flex-1 bg-surface-700 border border-surface-600 rounded-md px-2 py-0.5 text-[10px] text-text-primary outline-none cursor-pointer"
      >
        {(def.options ?? []).map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </WidgetWrapper>
  );
}

function InlineToggle({ def, value, onChange }: { def: InlineWidgetDef; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <WidgetWrapper>
      <span className="text-[10px] text-text-muted w-16 shrink-0 truncate">{def.label || def.key.replace(/_/g, ' ')}</span>
      <button
        onClick={() => onChange(!value)}
        className={`nodrag nopan relative w-8 h-4 rounded-full transition-colors ${value ? 'bg-accent-500' : 'bg-surface-600'}`}
      >
        <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-transform ${value ? 'translate-x-4' : 'translate-x-0.5'}`} />
      </button>
      <span className="text-[10px] text-text-secondary">{value ? 'on' : 'off'}</span>
    </WidgetWrapper>
  );
}

function InlineNumber({ def, value, onChange }: { def: InlineWidgetDef; value: number; onChange: (v: number) => void }) {
  return (
    <WidgetWrapper>
      <span className="text-[10px] text-text-muted w-16 shrink-0 truncate">{def.label || def.key.replace(/_/g, ' ')}</span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(Math.max(def.min ?? 0, value - (def.step ?? 1)))}
          className="nodrag nopan w-5 h-5 rounded-md bg-surface-700 hover:bg-surface-600 text-text-secondary text-xs flex items-center justify-center"
        >-</button>
        <span className="text-[10px] text-text-primary w-7 text-center tabular-nums">{value}</span>
        <button
          onClick={() => onChange(Math.min(def.max ?? 9999, value + (def.step ?? 1)))}
          className="nodrag nopan w-5 h-5 rounded-md bg-surface-700 hover:bg-surface-600 text-text-secondary text-xs flex items-center justify-center"
        >+</button>
      </div>
    </WidgetWrapper>
  );
}

function InlineWidget({ nodeId, def, config }: { nodeId: string; def: InlineWidgetDef; config: Record<string, unknown> }) {
  const updateNodeConfig = usePipelineEditorStore(s => s.updateNodeConfig);
  const value = config[def.key] ?? def.min ?? 0;

  const handleChange = useCallback((newVal: unknown) => {
    updateNodeConfig(nodeId, { ...config, [def.key]: newVal });
  }, [nodeId, config, def.key, updateNodeConfig]);

  switch (def.type) {
    case 'slider':  return <InlineSlider def={def} value={Number(value)} onChange={handleChange as (v: number) => void} />;
    case 'select':  return <InlineSelect def={def} value={String(value)} onChange={handleChange as (v: string) => void} />;
    case 'toggle':  return <InlineToggle def={def} value={Boolean(value)} onChange={handleChange as (v: boolean) => void} />;
    case 'number':  return <InlineNumber def={def} value={Number(value)} onChange={handleChange as (v: number) => void} />;
    default:        return null;
  }
}

/* ── Execution Status ─────────────────────────── */

type ExecStatus = 'pending' | 'running' | 'completed' | 'failed' | null;

const EXEC_BORDER: Record<string, string> = {
  pending:   'border-surface-600 opacity-60',
  running:   'border-cyan-400 shadow-md shadow-cyan-400/20',
  completed: 'border-emerald-500',
  failed:    'border-red-500',
};

/* ── TypedNode ────────────────────────────────── */

function TypedNodeInner({ id, data, selected }: NodeProps) {
  const nodeData = data as unknown as PipelineNodeData;
  const execStatus = (nodeData as Record<string, unknown>).executionStatus as ExecStatus;
  const execDuration = (nodeData as Record<string, unknown>).executionDuration as number | undefined;
  const meta = CATEGORIES[nodeData.category] || DEFAULT_META;
  const Icon = meta.icon;

  const { inputs, outputs } = useMemo(
    () => getComponentPorts(nodeData.componentType, nodeData.category),
    [nodeData.componentType, nodeData.category]
  );

  const inlineWidgets = useMemo(
    () => INLINE_WIDGETS[nodeData.componentType] ?? [],
    [nodeData.componentType]
  );

  const dataInputs = inputs.filter(p => p.type !== 'metadata');
  const metadataInputs = inputs.filter(p => p.type === 'metadata');
  const dataOutputs = outputs.filter(p => p.type !== 'metadata');
  const metadataOutputs = outputs.filter(p => p.type === 'metadata');

  const maxDataPorts = Math.max(dataInputs.length, dataOutputs.length, 1);
  const hasMetadata = metadataInputs.length > 0 || metadataOutputs.length > 0;
  const maxMetaPorts = Math.max(metadataInputs.length, metadataOutputs.length);
  const hasWidgets = inlineWidgets.length > 0;

  const getPortTop = (index: number, isMetadata: boolean) => {
    const base = HEADER_HEIGHT + PORT_SECTION_PAD;
    if (isMetadata) {
      return base + (maxDataPorts * PORT_ROW_HEIGHT) + 14 + (index * PORT_ROW_HEIGHT);
    }
    return base + (index * PORT_ROW_HEIGHT);
  };

  // Determine border style
  let borderClass: string;
  if (execStatus && EXEC_BORDER[execStatus]) {
    borderClass = `border-2 ${EXEC_BORDER[execStatus]}`;
  } else if (selected) {
    borderClass = 'border-2 border-accent-500 shadow-md shadow-accent-500/15';
  } else {
    borderClass = 'border border-border-primary shadow-sm hover:shadow-md hover:border-border-hover';
  }

  return (
    <div
      className={`rounded-2xl bg-surface-800 transition-all duration-150 ${borderClass}`}
      style={{ width: NODE_WIDTH }}
    >
      {/* Header - flat color, not gradient */}
      <div
        className={`${meta.bg} px-3 py-2 rounded-t-[14px] flex items-center gap-2`}
        style={{ height: HEADER_HEIGHT }}
      >
        <Icon className="w-4 h-4 text-white/90 shrink-0" />
        <span className="text-[11px] font-semibold text-white tracking-wide truncate flex-1">
          {nodeData.label}
        </span>
        {/* Execution badge */}
        {execStatus === 'running' && <Loader2 className="w-3.5 h-3.5 text-white animate-spin shrink-0" />}
        {execStatus === 'completed' && <CheckCircle className="w-3.5 h-3.5 text-emerald-300 shrink-0" />}
        {execStatus === 'failed' && <XCircle className="w-3.5 h-3.5 text-red-300 shrink-0" />}
        {execStatus === 'completed' && execDuration != null && (
          <span className="text-[9px] text-white/60 tabular-nums shrink-0">{execDuration.toFixed(0)}ms</span>
        )}
        {!execStatus && (
          <span className="text-[9px] text-white/50 uppercase tracking-wider font-medium shrink-0">
            {meta.label}
          </span>
        )}
      </div>

      {/* Ports section */}
      <div className="relative" style={{ paddingTop: PORT_SECTION_PAD, paddingBottom: hasWidgets ? 0 : BOTTOM_PADDING }}>
        {Array.from({ length: maxDataPorts }).map((_, i) => (
          <div key={`data-${i}`} className="flex items-center justify-between px-3" style={{ height: PORT_ROW_HEIGHT }}>
            <div>{dataInputs[i] && <PortDot port={dataInputs[i]} side="left" />}</div>
            <div>{dataOutputs[i] && <PortDot port={dataOutputs[i]} side="right" />}</div>
          </div>
        ))}

        {hasMetadata && (
          <div className="mx-3 my-1.5 border-t border-dashed border-surface-600/60" />
        )}

        {Array.from({ length: maxMetaPorts }).map((_, i) => (
          <div key={`meta-${i}`} className="flex items-center justify-between px-3" style={{ height: PORT_ROW_HEIGHT }}>
            <div>{metadataInputs[i] && <PortDot port={metadataInputs[i]} side="left" />}</div>
            <div>{metadataOutputs[i] && <PortDot port={metadataOutputs[i]} side="right" />}</div>
          </div>
        ))}
      </div>

      {/* Inline widgets */}
      {hasWidgets && (
        <div className="px-3 pb-2.5 pt-1.5 space-y-1 border-t border-surface-700/40">
          {inlineWidgets.map(def => (
            <div key={def.key} style={{ height: WIDGET_ROW_HEIGHT }} className="flex items-center">
              <InlineWidget nodeId={id} def={def} config={nodeData.config} />
            </div>
          ))}
        </div>
      )}

      {/* XYFlow Handles */}
      {dataInputs.map((port, i) => (
        <Handle key={`in-${port.name}`} id={`in-${port.name}`} type="target" position={Position.Left}
          style={{ top: getPortTop(i, false), background: PORT_COLORS[port.type] || PORT_COLORS.any, border: '2px solid var(--color-surface-800)', width: 11, height: 11 }} />
      ))}
      {metadataInputs.map((port, i) => (
        <Handle key={`in-${port.name}`} id={`in-${port.name}`} type="target" position={Position.Left}
          style={{ top: getPortTop(i, true), background: PORT_COLORS[port.type] || PORT_COLORS.any, border: '2px solid var(--color-surface-800)', width: 9, height: 9 }} />
      ))}
      {dataOutputs.map((port, i) => (
        <Handle key={`out-${port.name}`} id={`out-${port.name}`} type="source" position={Position.Right}
          style={{ top: getPortTop(i, false), background: PORT_COLORS[port.type] || PORT_COLORS.any, border: '2px solid var(--color-surface-800)', width: 11, height: 11 }} />
      ))}
      {metadataOutputs.map((port, i) => (
        <Handle key={`out-${port.name}`} id={`out-${port.name}`} type="source" position={Position.Right}
          style={{ top: getPortTop(i, true), background: PORT_COLORS[port.type] || PORT_COLORS.any, border: '2px solid var(--color-surface-800)', width: 9, height: 9 }} />
      ))}

      {/* Fallback hidden handles */}
      {inputs.length === 0 && (
        <Handle id="in-default" type="target" position={Position.Left}
          style={{ top: HEADER_HEIGHT + PORT_SECTION_PAD + PORT_ROW_HEIGHT / 2, background: meta.accent, border: '2px solid var(--color-surface-800)', width: 11, height: 11, opacity: 0 }} />
      )}
      {outputs.length === 0 && (
        <Handle id="out-default" type="source" position={Position.Right}
          style={{ top: HEADER_HEIGHT + PORT_SECTION_PAD + PORT_ROW_HEIGHT / 2, background: meta.accent, border: '2px solid var(--color-surface-800)', width: 11, height: 11, opacity: 0 }} />
      )}
    </div>
  );
}

export const TypedNode = memo(TypedNodeInner);
