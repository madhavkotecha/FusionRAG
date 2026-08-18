import YAML from 'yaml';
import type { Node, Edge } from '@xyflow/react';
import type { PipelineNodeData } from '../types/pipeline';

export function yamlToPipeline(yamlStr: string): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const parsed = YAML.parse(yamlStr);
  if (!parsed || !parsed.nodes) return { nodes: [], edges: [] };

  const nodes: Node<PipelineNodeData>[] = parsed.nodes.map((n: Record<string, unknown>) => {
    const isComposite = Boolean(n.is_composite || (n.data as Record<string, unknown>)?.is_composite);
    const steps = (n.steps || (n.data as Record<string, unknown>)?.steps) as unknown[] | undefined;
    return {
      id: n.id as string,
      type: isComposite ? 'composite' : (n.category as string),
      position: {
        x: ((n.position as Record<string, number>)?.x) ?? 0,
        y: ((n.position as Record<string, number>)?.y) ?? 0,
      },
      data: {
        label: (n.label as string) || (n.type as string),
        componentType: n.type as string,
        category: n.category as string,
        config: (n.config as Record<string, unknown>) || {},
        ...(isComposite ? { isComposite: true, steps, isExpanded: false } : {}),
      },
    };
  });

  const edges: Edge[] = (
    (parsed.edges as Record<string, unknown>[]) || []
  ).map((e: Record<string, unknown>, i: number) => ({
    id: `e-${e.source}-${e.target}-${i}`,
    source: e.source as string,
    target: e.target as string,
    sourceHandle: e.sourceHandle as string | undefined,
    targetHandle: e.targetHandle as string | undefined,
  }));

  return { nodes, edges };
}
