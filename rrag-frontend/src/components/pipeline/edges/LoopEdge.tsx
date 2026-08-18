import { type EdgeProps, getBezierPath, EdgeLabelRenderer } from '@xyflow/react';
import { RotateCcw } from 'lucide-react';

/**
 * Loop edge for feedback cycles (e.g., Reflection Agent → Retriever retry loop).
 * Renders as a curved dashed line with a rotation icon and iteration badge.
 */
export function LoopEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  data,
}: EdgeProps) {
  const maxIterations = Number((data as Record<string, unknown>)?.maxIterations ?? 3);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{
          ...style,
          stroke: '#e11d48',
          strokeWidth: 2,
          strokeDasharray: '8 4',
          fill: 'none',
          filter: 'drop-shadow(0 0 3px rgba(225, 29, 72, 0.3))',
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="flex items-center gap-1 bg-surface-800 border border-rose-500/30 rounded-full px-2 py-0.5"
        >
          <RotateCcw className="w-2.5 h-2.5 text-rose-400" />
          <span className="text-[9px] text-rose-300 font-medium">max {maxIterations}</span>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
