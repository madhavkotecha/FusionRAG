import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type OnConnect,
  type OnConnectEnd,
  type Connection,
  addEdge,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent as ReactMouseEvent } from 'react';
import { usePipelineEditorStore } from '../../stores/pipeline-editor.store';
import { TypedNode } from './nodes/TypedNode';
import CompositeNode from './nodes/CompositeNode';
import { GroupNode } from './nodes/GroupNode';
import { LoopEdge } from './edges/LoopEdge';
import { ContextMenu, type ContextMenuState } from './ContextMenu';
import { NodeContextMenu, type NodeContextMenuState } from './NodeContextMenu';
import { getComponentPorts, isConnectionValid, PORT_COLORS, type PortType } from '../../lib/port-types';
import type { PipelineNodeData } from '../../types/pipeline';
import type { NodeRunState } from '../../hooks/usePipelineRunStream';

const nodeTypes = {
  data_source: TypedNode,
  chunker: TypedNode,
  embedder: TypedNode,
  retriever: TypedNode,
  reranker: TypedNode,
  generator: TypedNode,
  parser: TypedNode,
  extractor: TypedNode,
  indexer: TypedNode,
  graph_builder: TypedNode,
  storage: TypedNode,
  agent: TypedNode,
  planner: TypedNode,
  composite: CompositeNode,
  group: GroupNode,
  // Dify-inspired node types
  knowledge_retrieval: TypedNode,
  llm: TypedNode,
  if_else: TypedNode,
  loop_node: TypedNode,
  code: TypedNode,
  http_request: TypedNode,
  human_input: TypedNode,
  control: TypedNode,
};

const edgeTypes = {
  loop: LoopEdge,
};

const defaultEdgeOptions = {
  animated: true,
  style: { stroke: '#4d65ff', strokeWidth: 2 },
};

/** Resolve port type from a handle id and node data */
function resolvePortType(handleId: string | null | undefined, nodeData: PipelineNodeData, direction: 'input' | 'output'): PortType | null {
  if (!handleId) return null;
  const ports = getComponentPorts(nodeData.componentType, nodeData.category);
  const list = direction === 'input' ? ports.inputs : ports.outputs;
  const prefix = direction === 'input' ? 'in-' : 'out-';
  const portName = handleId.startsWith(prefix) ? handleId.slice(prefix.length) : handleId;
  const port = list.find(p => p.name === portName);
  return port?.type ?? null;
}

interface PipelineCanvasProps {
  /** Map of node execution states from usePipelineRunStream — optional */
  nodeExecutionStates?: Map<string, NodeRunState>;
}

function PipelineCanvasInner({ nodeExecutionStates }: PipelineCanvasProps) {
  const { nodes, edges, onNodesChange, onEdgesChange, setSelectedNode, addNode, selectedNodeId } =
    usePipelineEditorStore();
  const { undo, redo, removeNode, duplicateNode, groupSelectedNodes, getSelectedNodeIds } = usePipelineEditorStore();
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [nodeContextMenu, setNodeContextMenu] = useState<NodeContextMenuState | null>(null);
  const connectingRef = useRef<{ nodeId: string; handleId: string; portType: PortType | null } | null>(null);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  // Inject execution status into node data so TypedNode can render overlays
  const styledNodes = useMemo(() => {
    if (!nodeExecutionStates || nodeExecutionStates.size === 0) return nodes;
    return nodes.map(node => {
      const execState = nodeExecutionStates.get(node.id);
      if (!execState) return node;
      return {
        ...node,
        data: {
          ...node.data,
          executionStatus: execState.status,
          executionDuration: execState.durationMs,
        },
      };
    });
  }, [nodes, nodeExecutionStates]);

  /* ── Connection handling ─────────────────────── */

  const onConnect: OnConnect = useCallback((connection: Connection) => {
    const sourceNode = usePipelineEditorStore.getState().nodes.find(n => n.id === connection.source);
    const targetNode = usePipelineEditorStore.getState().nodes.find(n => n.id === connection.target);

    if (sourceNode && targetNode) {
      const sourceData = sourceNode.data as unknown as PipelineNodeData;
      const targetData = targetNode.data as unknown as PipelineNodeData;
      const sourceType = resolvePortType(connection.sourceHandle, sourceData, 'output');
      const targetType = resolvePortType(connection.targetHandle, targetData, 'input');

      if (sourceType && targetType && !isConnectionValid(sourceType, targetType)) {
        console.warn(`Invalid connection: ${sourceType} → ${targetType}`);
        return;
      }

      const edgeColor = sourceType ? PORT_COLORS[sourceType] : '#4d65ff';
      usePipelineEditorStore.setState((state) => ({
        edges: addEdge(
          { ...connection, style: { stroke: edgeColor, strokeWidth: 2 } },
          state.edges
        ),
        isDirty: true,
      }));
    } else {
      usePipelineEditorStore.setState((state) => ({
        edges: addEdge(connection, state.edges),
        isDirty: true,
      }));
    }
  }, []);

  // Track which port we're dragging from
  const onConnectStart = useCallback((_: unknown, params: { nodeId: string | null; handleId: string | null; handleType: string | null }) => {
    if (!params.nodeId || !params.handleId) return;
    const node = usePipelineEditorStore.getState().nodes.find(n => n.id === params.nodeId);
    if (!node) return;
    const nodeData = node.data as unknown as PipelineNodeData;
    const portType = resolvePortType(params.handleId, nodeData, params.handleType === 'source' ? 'output' : 'input');
    connectingRef.current = { nodeId: params.nodeId, handleId: params.handleId, portType };
  }, []);

  // When dropping a connection on empty canvas, open connection-aware context menu
  const onConnectEnd: OnConnectEnd = useCallback((event: MouseEvent | TouchEvent) => {
    const target = (event as MouseEvent).target as HTMLElement;
    // Only trigger if dropped on the pane (not on a node)
    if (!target?.classList?.contains('react-flow__pane') && !target?.closest('.react-flow__pane')) {
      connectingRef.current = null;
      return;
    }
    if (!connectingRef.current?.portType) {
      connectingRef.current = null;
      return;
    }

    const clientX = 'clientX' in event ? event.clientX : (event as TouchEvent).touches[0].clientX;
    const clientY = 'clientY' in event ? event.clientY : (event as TouchEvent).touches[0].clientY;
    const flowPos = screenToFlowPosition({ x: clientX, y: clientY });

    setContextMenu({
      x: clientX,
      y: clientY,
      canvasX: flowPos.x,
      canvasY: flowPos.y,
      compatibleWithOutputType: connectingRef.current.portType,
    });
    connectingRef.current = null;
  }, [screenToFlowPosition]);

  /* ── Drag & Drop from palette ────────────────── */

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData('application/reactflow');
      if (!raw) return;

      let parsed: Record<string, unknown>;
      try { parsed = JSON.parse(raw); } catch { return; }
      if (!parsed.type || !parsed.category || !parsed.label) return;

      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      const isComposite = Boolean(parsed.isComposite || parsed.is_composite);
      const steps = (parsed.steps ?? []) as unknown[];
      addNode(
        parsed.type as string,
        parsed.category as string,
        parsed.label as string,
        position,
        isComposite ? { isComposite, steps } : undefined,
      );
    },
    [addNode, screenToFlowPosition]
  );

  /* ── Right-click context menu ────────────────── */

  const onContextMenu = useCallback((event: ReactMouseEvent) => {
    event.preventDefault();
    const flowPos = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    setContextMenu({ x: event.clientX, y: event.clientY, canvasX: flowPos.x, canvasY: flowPos.y });
  }, [screenToFlowPosition]);

  const handleContextMenuSelect = useCallback(
    (type: string, category: string, label: string) => {
      if (!contextMenu) return;
      addNode(type, category, label, { x: contextMenu.canvasX, y: contextMenu.canvasY });
      setContextMenu(null);
    },
    [contextMenu, addNode]
  );

  /* ── Keyboard shortcuts ──────────────────────── */

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when typing in input/textarea/select
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

      const ctrl = e.ctrlKey || e.metaKey;

      // Ctrl+Z = Undo
      if (ctrl && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
        return;
      }

      // Ctrl+Y or Ctrl+Shift+Z = Redo
      if ((ctrl && e.key === 'y') || (ctrl && e.key === 'z' && e.shiftKey)) {
        e.preventDefault();
        redo();
        return;
      }

      // Delete / Backspace = Delete selected node or selected edges
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        if (selectedNodeId) {
          removeNode(selectedNodeId);
        }
        // Also remove any selected edges
        const state = usePipelineEditorStore.getState();
        const selectedEdges = state.edges.filter(edge => edge.selected);
        if (selectedEdges.length > 0) {
          usePipelineEditorStore.setState(s => ({
            edges: s.edges.filter(edge => !edge.selected),
            isDirty: true,
          }));
        }
        return;
      }

      // Ctrl+D = Duplicate selected node
      if (ctrl && e.key === 'd' && selectedNodeId) {
        e.preventDefault();
        duplicateNode(selectedNodeId);
        return;
      }

      // Ctrl+G = Group selected nodes
      if (ctrl && e.key === 'g') {
        e.preventDefault();
        const selectedIds = getSelectedNodeIds();
        if (selectedIds.length >= 2) {
          const name = prompt('Group name:');
          if (name) groupSelectedNodes(name);
        }
        return;
      }

      // Space or / = Open context menu at center
      if (e.key === ' ' && !ctrl) {
        e.preventDefault();
        const rect = reactFlowWrapper.current?.getBoundingClientRect();
        if (rect) {
          const cx = rect.left + rect.width / 2;
          const cy = rect.top + rect.height / 2;
          const flowPos = screenToFlowPosition({ x: cx, y: cy });
          setContextMenu({ x: cx, y: cy, canvasX: flowPos.x, canvasY: flowPos.y });
        }
        return;
      }

      // F = Fit view (handled natively by react-flow if we don't capture it)
      // Escape = deselect
      if (e.key === 'Escape') {
        setSelectedNode(null);
        setContextMenu(null);
        return;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedNodeId, undo, redo, removeNode, duplicateNode, setSelectedNode, screenToFlowPosition, groupSelectedNodes, getSelectedNodeIds]);

  /* ── Minimap colors ──────────────────────────── */

  const miniMapNodeColor = useCallback((node: { data?: Record<string, unknown> }) => {
    const d = node.data as (PipelineNodeData & { executionStatus?: string }) | undefined;
    // During execution, show status colors
    if (d?.executionStatus) {
      const statusColors: Record<string, string> = {
        pending: '#6b7280', running: '#06b6d4', completed: '#10b981', failed: '#ef4444',
      };
      return statusColors[d.executionStatus] ?? '#1e40af';
    }
    if (!d?.category) return '#1e40af';
    const colorMap: Record<string, string> = {
      parser: '#64748b', chunker: '#10b981', embedder: '#a855f7',
      extractor: '#14b8a6', graph_builder: '#ec4899', indexer: '#6366f1',
      storage: '#78716c', retriever: '#f97316', reranker: '#f59e0b',
      generator: '#f43f5e', agent: '#8b5cf6', planner: '#06b6d4',
    };
    return colorMap[d.category] ?? '#1e40af';
  }, []);

  return (
    <div ref={reactFlowWrapper} className="h-full w-full bg-surface-950">
      <ReactFlow
        nodes={styledNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onConnectStart={onConnectStart}
        onConnectEnd={onConnectEnd}
        onNodeClick={(_, node) => { setSelectedNode(node.id); setNodeContextMenu(null); }}
        onNodeContextMenu={(event, node) => {
          event.preventDefault();
          setNodeContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
          setContextMenu(null);
        }}
        onPaneClick={() => { setSelectedNode(null); setContextMenu(null); setNodeContextMenu(null); }}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onContextMenu={onContextMenu}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
        fitView
        deleteKeyCode={null}
        edgesReconnectable
        edgesFocusable
      >
        <Background variant={BackgroundVariant.Dots} color="#252530" gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeColor={miniMapNodeColor}
          maskColor="rgba(0,0,0,0.7)"
          pannable
          zoomable
        />
      </ReactFlow>
      {contextMenu && (
        <ContextMenu
          state={contextMenu}
          onSelect={handleContextMenuSelect}
          onClose={() => setContextMenu(null)}
        />
      )}
      {nodeContextMenu && (
        <NodeContextMenu
          state={nodeContextMenu}
          onClose={() => setNodeContextMenu(null)}
          onGroup={getSelectedNodeIds().length >= 2 ? () => {
            const name = prompt('Group name:');
            if (name) groupSelectedNodes(name);
          } : undefined}
        />
      )}
    </div>
  );
}

export function PipelineCanvas({ nodeExecutionStates }: PipelineCanvasProps = {}) {
  return <PipelineCanvasInner nodeExecutionStates={nodeExecutionStates} />;
}
