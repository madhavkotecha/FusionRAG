import { create } from 'zustand';
import type { Node, Edge, OnNodesChange, OnEdgesChange, XYPosition } from '@xyflow/react';
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import type { PipelineNodeData, PipelineType } from '../types/pipeline';
import { pipelineToYaml } from '../lib/pipeline-to-yaml';
import { yamlToPipeline } from '../lib/yaml-to-pipeline';
import { getComponentPorts, type PortDefinition } from '../lib/port-types';

interface Snapshot {
  nodes: Node<PipelineNodeData>[];
  edges: Edge[];
}

interface PipelineEditorState {
  nodes: Node<PipelineNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;
  yamlSource: string;
  isDirty: boolean;
  syncSource: 'canvas' | 'yaml' | null;
  yamlError: string | null;
  pipelineType: PipelineType;
  datastoreId: string | null;
  /** When set, save/load uses the ingestion query-pipeline API instead of pipeline service */
  queryPipelineId: string | null;

  // Undo/Redo
  undoStack: Snapshot[];
  redoStack: Snapshot[];

  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  setSelectedNode: (id: string | null) => void;
  addNode: (type: string, category: string, label: string, position: XYPosition, extra?: { isComposite?: boolean; steps?: unknown[] }) => void;
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void;
  removeNode: (nodeId: string) => void;
  duplicateNode: (nodeId: string) => void;
  setYamlSource: (yaml: string) => void;
  syncFromYaml: (yaml: string) => void;
  syncToYaml: () => void;
  loadPipeline: (
    nodes: Node<PipelineNodeData>[],
    edges: Edge[],
    pipelineType?: PipelineType,
    datastoreId?: string | null,
    queryPipelineId?: string | null,
  ) => void;
  clear: () => void;
  undo: () => void;
  redo: () => void;
  groupSelectedNodes: (name: string) => void;
  getSelectedNodeIds: () => string[];
}

const MAX_UNDO = 50;

function pushUndo(state: { nodes: Node<PipelineNodeData>[]; edges: Edge[]; undoStack: Snapshot[]; redoStack: Snapshot[] }) {
  const snapshot: Snapshot = {
    nodes: structuredClone(state.nodes),
    edges: structuredClone(state.edges),
  };
  const stack = [...state.undoStack, snapshot];
  if (stack.length > MAX_UNDO) stack.shift();
  return { undoStack: stack, redoStack: [] as Snapshot[] };
}

export const usePipelineEditorStore = create<PipelineEditorState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  yamlSource: '',
  isDirty: false,
  syncSource: null,
  yamlError: null,
  pipelineType: 'ingestion',
  datastoreId: null,
  queryPipelineId: null,
  undoStack: [],
  redoStack: [],

  onNodesChange: (changes) => {
    set((state) => {
      const nodes = applyNodeChanges(changes, state.nodes) as Node<PipelineNodeData>[];
      const yamlSource = pipelineToYaml(nodes, state.edges);
      return { nodes, yamlSource, isDirty: true, syncSource: 'canvas' };
    });
  },

  onEdgesChange: (changes) => {
    set((state) => {
      const edges = applyEdgeChanges(changes, state.edges);
      const yamlSource = pipelineToYaml(state.nodes, edges);
      return { edges, yamlSource, isDirty: true, syncSource: 'canvas' };
    });
  },

  setSelectedNode: (id) => set({ selectedNodeId: id }),

  addNode: (type, category, label, position, extra) => {
    const isComposite = extra?.isComposite ?? false;
    const newNode: Node<PipelineNodeData> = {
      id: crypto.randomUUID(),
      type: isComposite ? 'composite' : category,
      position,
      data: {
        label,
        componentType: type,
        category,
        config: {},
        ...(isComposite ? { isComposite: true, steps: extra?.steps ?? [], isExpanded: false } : {}),
      },
    };
    set((state) => {
      const undo = pushUndo(state);
      const nodes = [...state.nodes, newNode];
      const yamlSource = pipelineToYaml(nodes, state.edges);
      return { ...undo, nodes, yamlSource, isDirty: true, syncSource: 'canvas' };
    });
  },

  updateNodeConfig: (nodeId, config) => {
    set((state) => {
      const nodes = state.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, config } }
          : node
      );
      const yamlSource = pipelineToYaml(nodes, state.edges);
      return { nodes, yamlSource, isDirty: true, syncSource: 'canvas' };
    });
  },

  removeNode: (nodeId) => {
    set((state) => {
      const undo = pushUndo(state);
      const nodes = state.nodes.filter((n) => n.id !== nodeId);
      const edges = state.edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId
      );
      const yamlSource = pipelineToYaml(nodes, edges);
      return { ...undo, nodes, edges, yamlSource, isDirty: true, syncSource: 'canvas', selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId };
    });
  },

  duplicateNode: (nodeId) => {
    set((state) => {
      const orig = state.nodes.find(n => n.id === nodeId);
      if (!orig) return {};
      const undo = pushUndo(state);
      const newNode: Node<PipelineNodeData> = {
        ...structuredClone(orig),
        id: crypto.randomUUID(),
        position: { x: orig.position.x + 40, y: orig.position.y + 40 },
        selected: false,
      };
      const nodes = [...state.nodes, newNode];
      const yamlSource = pipelineToYaml(nodes, state.edges);
      return { ...undo, nodes, yamlSource, isDirty: true, syncSource: 'canvas', selectedNodeId: newNode.id };
    });
  },

  setYamlSource: (yaml) => set({ yamlSource: yaml }),

  syncFromYaml: (yaml) => {
    try {
      const { nodes, edges } = yamlToPipeline(yaml);
      set((state) => {
        const undo = pushUndo(state);
        return {
          ...undo,
          nodes,
          edges,
          yamlSource: yaml,
          isDirty: true,
          syncSource: 'yaml',
          yamlError: null,
        };
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Invalid YAML';
      set({ yamlSource: yaml, yamlError: msg });
    }
  },

  syncToYaml: () => {
    const { nodes, edges } = get();
    const yamlSource = pipelineToYaml(nodes, edges);
    set({ yamlSource, syncSource: 'canvas', yamlError: null });
  },

  loadPipeline: (nodes, edges, pipelineType, datastoreId, queryPipelineId) => {
    // Detect composite nodes and set correct ReactFlow type
    const processedNodes = nodes.map((node) => {
      const data = node.data as Record<string, unknown>;
      const isComposite = Boolean(data?.isComposite || data?.is_composite);
      if (isComposite && node.type !== 'composite') {
        return {
          ...node,
          type: 'composite' as const,
          data: { ...node.data, isComposite: true, isExpanded: false },
        } as typeof node;
      }
      return node;
    });
    const yamlSource = pipelineToYaml(processedNodes, edges);
    set({
      nodes: processedNodes,
      edges,
      yamlSource,
      isDirty: false,
      syncSource: null,
      selectedNodeId: null,
      yamlError: null,
      pipelineType: pipelineType ?? 'ingestion',
      datastoreId: datastoreId ?? null,
      queryPipelineId: queryPipelineId ?? null,
      undoStack: [],
      redoStack: [],
    });
  },

  clear: () => {
    set({
      nodes: [],
      edges: [],
      yamlSource: '',
      isDirty: false,
      syncSource: null,
      selectedNodeId: null,
      yamlError: null,
      pipelineType: 'ingestion',
      datastoreId: null,
      queryPipelineId: null,
      undoStack: [],
      redoStack: [],
    });
  },

  undo: () => {
    set((state) => {
      if (state.undoStack.length === 0) return {};
      const stack = [...state.undoStack];
      const prev = stack.pop()!;
      const redoSnapshot: Snapshot = { nodes: structuredClone(state.nodes), edges: structuredClone(state.edges) };
      const yamlSource = pipelineToYaml(prev.nodes, prev.edges);
      return {
        nodes: prev.nodes,
        edges: prev.edges,
        undoStack: stack,
        redoStack: [...state.redoStack, redoSnapshot],
        yamlSource,
        isDirty: true,
        syncSource: 'canvas',
      };
    });
  },

  redo: () => {
    set((state) => {
      if (state.redoStack.length === 0) return {};
      const stack = [...state.redoStack];
      const next = stack.pop()!;
      const undoSnapshot: Snapshot = { nodes: structuredClone(state.nodes), edges: structuredClone(state.edges) };
      const yamlSource = pipelineToYaml(next.nodes, next.edges);
      return {
        nodes: next.nodes,
        edges: next.edges,
        redoStack: stack,
        undoStack: [...state.undoStack, undoSnapshot],
        yamlSource,
        isDirty: true,
        syncSource: 'canvas',
      };
    });
  },

  groupSelectedNodes: (name: string) => {
    set((state) => {
      const selectedIds = state.nodes.filter(n => n.selected).map(n => n.id);
      if (selectedIds.length < 2) return {};

      const undo = pushUndo(state);
      const selectedSet = new Set(selectedIds);
      const innerNodes = state.nodes.filter(n => selectedSet.has(n.id));
      const innerEdges = state.edges.filter(e => selectedSet.has(e.source) && selectedSet.has(e.target));
      const externalEdgesIn = state.edges.filter(e => !selectedSet.has(e.source) && selectedSet.has(e.target));
      const externalEdgesOut = state.edges.filter(e => selectedSet.has(e.source) && !selectedSet.has(e.target));

      // Derive group input ports from external incoming edges
      const groupInputPorts: PortDefinition[] = [];
      const seenInputs = new Set<string>();
      for (const edge of externalEdgesIn) {
        const targetNode = innerNodes.find(n => n.id === edge.target);
        if (!targetNode) continue;
        const ports = getComponentPorts((targetNode.data as PipelineNodeData).componentType, (targetNode.data as PipelineNodeData).category);
        const handleName = edge.targetHandle?.replace('in-', '') ?? '';
        const port = ports.inputs.find(p => p.name === handleName);
        if (port && !seenInputs.has(port.name)) {
          groupInputPorts.push(port);
          seenInputs.add(port.name);
        }
      }

      // Derive group output ports from external outgoing edges
      const groupOutputPorts: PortDefinition[] = [];
      const seenOutputs = new Set<string>();
      for (const edge of externalEdgesOut) {
        const sourceNode = innerNodes.find(n => n.id === edge.source);
        if (!sourceNode) continue;
        const ports = getComponentPorts((sourceNode.data as PipelineNodeData).componentType, (sourceNode.data as PipelineNodeData).category);
        const handleName = edge.sourceHandle?.replace('out-', '') ?? '';
        const port = ports.outputs.find(p => p.name === handleName);
        if (port && !seenOutputs.has(port.name)) {
          groupOutputPorts.push(port);
          seenOutputs.add(port.name);
        }
      }

      // If no external edges, fall back to first/last node ports
      if (groupInputPorts.length === 0 && innerNodes.length > 0) {
        const first = innerNodes[0].data as PipelineNodeData;
        const fp = getComponentPorts(first.componentType, first.category);
        if (fp.inputs.length > 0) groupInputPorts.push(fp.inputs[0]);
      }
      if (groupOutputPorts.length === 0 && innerNodes.length > 0) {
        const last = innerNodes[innerNodes.length - 1].data as PipelineNodeData;
        const lp = getComponentPorts(last.componentType, last.category);
        if (lp.outputs.length > 0) groupOutputPorts.push(lp.outputs[0]);
      }

      // Calculate group position (center of selected nodes)
      const avgX = innerNodes.reduce((s, n) => s + n.position.x, 0) / innerNodes.length;
      const avgY = innerNodes.reduce((s, n) => s + n.position.y, 0) / innerNodes.length;

      const groupId = crypto.randomUUID();
      const groupNode: Node<PipelineNodeData> = {
        id: groupId,
        type: 'group',
        position: { x: avgX, y: avgY },
        data: {
          label: name,
          componentType: 'group',
          category: 'group',
          config: {},
          innerNodeCount: innerNodes.length,
          innerSummary: innerNodes.map(n => (n.data as PipelineNodeData).label).join(' → '),
          groupInputPorts,
          groupOutputPorts,
          isExpanded: false,
          // Store inner structure for future expansion
          _innerNodes: innerNodes,
          _innerEdges: innerEdges,
        } as unknown as PipelineNodeData,
      };

      // Remove inner nodes, keep external nodes, add group node
      const remainingNodes = state.nodes.filter(n => !selectedSet.has(n.id));
      const newNodes = [...remainingNodes, groupNode];

      // Rewire external edges to point to/from group node
      const newEdges = state.edges
        .filter(e => !selectedSet.has(e.source) || !selectedSet.has(e.target))  // remove inner edges
        .filter(e => !(selectedSet.has(e.source) && !selectedSet.has(e.target)) && !(selectedSet.has(e.target) && !selectedSet.has(e.source))) // remove external edges too (we'll rewire)
        ;

      // Add rewired external edges
      for (const edge of externalEdgesIn) {
        const handleName = edge.targetHandle?.replace('in-', '') ?? 'default';
        newEdges.push({ ...edge, id: `${edge.id}-grp`, target: groupId, targetHandle: `in-${handleName}` });
      }
      for (const edge of externalEdgesOut) {
        const handleName = edge.sourceHandle?.replace('out-', '') ?? 'default';
        newEdges.push({ ...edge, id: `${edge.id}-grp`, source: groupId, sourceHandle: `out-${handleName}` });
      }

      const yamlSource = pipelineToYaml(newNodes, newEdges);
      return { ...undo, nodes: newNodes, edges: newEdges, yamlSource, isDirty: true, syncSource: 'canvas', selectedNodeId: groupId };
    });
  },

  getSelectedNodeIds: () => {
    return get().nodes.filter(n => n.selected).map(n => n.id);
  },
}));
