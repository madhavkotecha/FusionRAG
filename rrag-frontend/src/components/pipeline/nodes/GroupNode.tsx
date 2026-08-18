import { Handle, Position, type NodeProps } from '@xyflow/react';
import { memo } from 'react';
import { Package } from 'lucide-react';
import { PORT_COLORS } from '../../../lib/port-types';
import type { PortDefinition } from '../../../lib/port-types';

export interface GroupNodeData {
  label: string;
  componentType: 'group';
  category: 'group';
  config: Record<string, unknown>;
  /** Number of inner nodes */
  innerNodeCount: number;
  /** Summary of inner node labels */
  innerSummary: string;
  /** Derived input ports from unconnected inner-node inputs */
  groupInputPorts: PortDefinition[];
  /** Derived output ports from unconnected inner-node outputs */
  groupOutputPorts: PortDefinition[];
  /** Whether expanded to show inner nodes (future) */
  isExpanded: boolean;
}

const HEADER_HEIGHT = 36;
const PORT_ROW_HEIGHT = 26;
const PORT_SECTION_PAD = 8;
const BODY_PAD = 8;

function GroupNodeInner({ data, selected }: NodeProps) {
  const d = data as unknown as GroupNodeData;
  const inputs = d.groupInputPorts ?? [];
  const outputs = d.groupOutputPorts ?? [];
  const maxPorts = Math.max(inputs.length, outputs.length, 1);

  const getPortTop = (index: number) => HEADER_HEIGHT + PORT_SECTION_PAD + index * PORT_ROW_HEIGHT;

  return (
    <div
      className={`rounded-xl min-w-[240px] max-w-[300px] transition-all duration-200 ${
        selected
          ? 'ring-2 ring-accent-500 shadow-lg shadow-accent-500/20'
          : 'ring-1 ring-border-secondary shadow-lg shadow-black/30'
      } bg-surface-800 border border-dashed border-accent-500/30`}
    >
      {/* Header */}
      <div
        className="bg-gradient-to-r from-accent-600 to-accent-500 px-3 py-2 rounded-t-xl flex items-center gap-2"
        style={{ height: HEADER_HEIGHT }}
      >
        <Package className="w-3.5 h-3.5 text-white/90 shrink-0" />
        <span className="text-[10px] font-semibold text-white/90 tracking-wide truncate flex-1">
          {d.label}
        </span>
        <span className="text-[8px] text-white/50 uppercase tracking-wider shrink-0">
          Group
        </span>
      </div>

      {/* Ports */}
      <div className="px-1" style={{ paddingTop: PORT_SECTION_PAD, paddingBottom: BODY_PAD }}>
        {Array.from({ length: maxPorts }).map((_, i) => (
          <div key={i} className="flex items-center justify-between" style={{ height: PORT_ROW_HEIGHT }}>
            <div className="px-2">
              {inputs[i] && (
                <div className="flex items-center gap-1.5">
                  <div className="rounded-full" style={{ width: 8, height: 8, backgroundColor: PORT_COLORS[inputs[i].type] }} />
                  <span className="text-[9px] text-text-secondary">{inputs[i].name.replace(/_/g, ' ')}</span>
                </div>
              )}
            </div>
            <div className="px-2">
              {outputs[i] && (
                <div className="flex items-center gap-1.5 flex-row-reverse">
                  <div className="rounded-full" style={{ width: 8, height: 8, backgroundColor: PORT_COLORS[outputs[i].type] }} />
                  <span className="text-[9px] text-text-secondary">{outputs[i].name.replace(/_/g, ' ')}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="px-3 pb-2 border-t border-surface-700/50">
        <div className="flex items-center gap-1.5 mt-1.5">
          <span className="text-[9px] text-text-muted">{d.innerNodeCount} nodes</span>
          <span className="text-[8px] text-text-muted/60 truncate">{d.innerSummary}</span>
        </div>
      </div>

      {/* Handles */}
      {inputs.map((port, i) => (
        <Handle key={`in-${port.name}`} id={`in-${port.name}`} type="target" position={Position.Left}
          style={{ top: getPortTop(i), background: PORT_COLORS[port.type], border: '2px solid var(--color-surface-800)', width: 10, height: 10 }} />
      ))}
      {outputs.map((port, i) => (
        <Handle key={`out-${port.name}`} id={`out-${port.name}`} type="source" position={Position.Right}
          style={{ top: getPortTop(i), background: PORT_COLORS[port.type], border: '2px solid var(--color-surface-800)', width: 10, height: 10 }} />
      ))}
      {inputs.length === 0 && (
        <Handle id="in-default" type="target" position={Position.Left}
          style={{ top: getPortTop(0), background: '#4d65ff', border: '2px solid var(--color-surface-800)', width: 10, height: 10 }} />
      )}
      {outputs.length === 0 && (
        <Handle id="out-default" type="source" position={Position.Right}
          style={{ top: getPortTop(0), background: '#4d65ff', border: '2px solid var(--color-surface-800)', width: 10, height: 10 }} />
      )}
    </div>
  );
}

export const GroupNode = memo(GroupNodeInner);
