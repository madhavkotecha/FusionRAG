import type { Node, Edge } from '@xyflow/react';

export interface PipelineNodeData {
  label: string;
  componentType: string;
  category: string;
  config: Record<string, unknown>;
  [key: string]: unknown;
}

export type PipelineNode = Node<PipelineNodeData>;
export type PipelineEdge = Edge;

export type PipelineType = 'ingestion' | 'query';

export interface Pipeline {
  id: string;
  workspaceId: string;
  name: string;
  description: string | null;
  definition: { nodes: PipelineNode[]; edges: PipelineEdge[] };
  status: 'draft' | 'published' | 'archived';
  pipelineType: PipelineType;
  datastoreId: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface PipelineVersion {
  id: string;
  pipelineId: string;
  version: number;
  definition: Record<string, unknown>;
  changeMessage: string | null;
  createdBy: string;
  createdAt: string;
}

export interface PipelineRun {
  id: string;
  pipelineId: string;
  versionId: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed';
  inputParams: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  error: string | null;
  startedAt: string | null;
  completedAt: string | null;
  createdBy: string;
  createdAt: string;
}

export interface ConfigSchemaProperty {
  type: string;
  default?: unknown;
  description?: string;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  items?: { type?: string; enum?: string[] };
  ui_widget?: 'text' | 'textarea' | 'password' | 'select' | 'slider' | 'toggle' | 'array' | 'json';
  ui_advanced?: boolean;
  ui_group?: string;
}

export interface ConfigSchema {
  type: string;
  properties?: Record<string, ConfigSchemaProperty>;
  required?: string[];
}

export interface StepDefinition {
  order: number;
  name: string;
  method: string;
  description?: string;
  retry?: number;
  retryCondition?: string;
  outputs?: string[];
  configSchema?: ConfigSchema;
}

export interface ComponentDefinition {
  type: string;
  category: string;
  name: string;
  description: string;
  configSchema: ConfigSchema;
  inputPorts: { name: string; type: string; description?: string }[];
  outputPorts: { name: string; type: string; description?: string }[];
  source?: 'seed' | 'custom';
  isComposite?: boolean;
  steps?: StepDefinition[];
  workspaceId?: string | null;
}

export interface CompositeNodeData extends PipelineNodeData {
  isComposite: true;
  steps: StepDefinition[];
  isExpanded: boolean;
}
