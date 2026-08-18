import YAML from 'yaml';
import type { Node, Edge } from '@xyflow/react';
import type { PipelineNodeData } from '../types/pipeline';

export function pipelineToYaml(nodes: Node<PipelineNodeData>[], edges: Edge[]): string {
  const pipeline = {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.data.componentType,
      category: node.data.category,
      label: node.data.label,
      config: node.data.config,
      position: { x: node.position.x, y: node.position.y },
    })),
    edges: edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
    })),
  };
  return YAML.stringify(pipeline);
}
