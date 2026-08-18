import { memo, useCallback, useState } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { ChevronDown, ChevronRight, RotateCw, GitBranch, Bot, Network, Search } from 'lucide-react';
import type { StepDefinition } from '../../../types/pipeline';

const CATEGORIES: Record<string, { gradient: string; handleColor: string; label: string; icon: React.ElementType }> = {
  graph_builder: { gradient: 'from-pink-600 to-pink-400', handleColor: '#ec4899', label: 'Graph Builder', icon: Network },
  retriever: { gradient: 'from-orange-600 to-orange-400', handleColor: '#f97316', label: 'Retriever', icon: Search },
  agent: { gradient: 'from-violet-600 to-violet-400', handleColor: '#8b5cf6', label: 'Agent', icon: Bot },
};

function StepItem({ step }: { step: StepDefinition }) {
  return (
    <div className="flex items-center gap-2 py-1 px-2 text-xs text-gray-300">
      <span className="text-gray-500 w-4 text-right">{step.order}.</span>
      <span className="flex-1 truncate">{step.name}</span>
      {step.retry && step.retry > 0 && (
        <span className="flex items-center gap-0.5 text-amber-400" title={`Retry up to ${step.retry}x`}>
          <RotateCw size={10} />
          <span>{step.retry}</span>
        </span>
      )}
      {step.outputs && step.outputs.length > 0 && (
        <span className="text-purple-400" title={`Routes: ${step.outputs.join(', ')}`}>
          <GitBranch size={10} />
        </span>
      )}
    </div>
  );
}

function CompositeNode({ data, id }: { data: Record<string, unknown>; id: string }) {
  const [isExpanded, setIsExpanded] = useState((data.isExpanded as boolean) ?? false);
  const updateNodeInternals = useUpdateNodeInternals();
  const category = data.category as string;
  const catMeta = CATEGORIES[category] || { gradient: 'from-gray-600 to-gray-400', handleColor: '#6b7280', label: category || 'Unknown', icon: Network };
  const Icon = catMeta.icon;

  const toggleExpand = useCallback(() => {
    setIsExpanded((prev: boolean) => {
      setTimeout(() => updateNodeInternals(id), 0);
      return !prev;
    });
  }, [id, updateNodeInternals]);

  const steps: StepDefinition[] = (data.steps as StepDefinition[]) || [];

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 shadow-lg min-w-[220px]">
      <Handle type="target" position={Position.Left} style={{ background: catMeta.handleColor }} />
      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-t-lg bg-gradient-to-r ${catMeta.gradient} cursor-pointer`}
        onClick={toggleExpand}
      >
        <Icon size={14} className="text-white/80" />
        <span className="text-sm font-medium text-white flex-1 truncate">{data.label as string}</span>
        <span className="text-xs text-white/60">{steps.length} steps</span>
        {isExpanded ? <ChevronDown size={14} className="text-white/60" /> : <ChevronRight size={14} className="text-white/60" />}
      </div>
      <div className="px-3 py-1 text-[10px] text-gray-500 uppercase tracking-wider">
        {catMeta.label} &middot; composite
      </div>
      {isExpanded && (
        <div className="border-t border-gray-800 py-1">
          {steps.map((step, i) => (
            <div key={step.method}>
              <StepItem step={step} />
              {i < steps.length - 1 && (
                <div className="flex justify-center">
                  <div className="w-px h-2 bg-gray-700" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: catMeta.handleColor }} />
    </div>
  );
}

export default memo(CompositeNode);
