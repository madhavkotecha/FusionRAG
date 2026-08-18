import { useEffect, useState } from 'react';

export interface StepState {
  order: number;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  durationMs?: number;
  retries?: number;
  route?: string;
}

export interface NodeRunState {
  nodeId: string;
  componentType: string;
  isComposite: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed';
  steps: StepState[];
  durationMs?: number;
  error?: string;
}

export function usePipelineRunStream(pipelineId: string | null, runId: string | null) {
  const [nodeStates, setNodeStates] = useState<Map<string, NodeRunState>>(new Map());
  const [runStatus, setRunStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');

  useEffect(() => {
    if (!pipelineId || !runId) return;
    const url = `/api/v1/pipelines/${pipelineId}/runs/${runId}/stream`;
    const es = new EventSource(url);
    setRunStatus('running');

    es.addEventListener('node_started', (e) => {
      const data = JSON.parse(e.data) as { node_id: string; component_type: string; is_composite?: boolean };
      setNodeStates((prev) => {
        const next = new Map(prev);
        next.set(data.node_id, {
          nodeId: data.node_id,
          componentType: data.component_type,
          isComposite: data.is_composite ?? false,
          status: 'running',
          steps: [],
        });
        return next;
      });
    });

    es.addEventListener('step_started', (e) => {
      const data = JSON.parse(e.data) as { node_id: string; step_order: number; step_name: string };
      setNodeStates((prev) => {
        const next = new Map(prev);
        const node = next.get(data.node_id);
        if (node) {
          node.steps.push({ order: data.step_order, name: data.step_name, status: 'running' });
        }
        return next;
      });
    });

    es.addEventListener('step_completed', (e) => {
      const data = JSON.parse(e.data) as { node_id: string; step_order: number; duration_ms?: number; retries?: number };
      setNodeStates((prev) => {
        const next = new Map(prev);
        const node = next.get(data.node_id);
        if (node) {
          const step = node.steps.find((s) => s.order === data.step_order);
          if (step) {
            step.status = 'completed';
            step.durationMs = data.duration_ms;
            step.retries = data.retries;
          }
        }
        return next;
      });
    });

    es.addEventListener('node_completed', (e) => {
      const data = JSON.parse(e.data) as { node_id: string; duration_ms?: number };
      setNodeStates((prev) => {
        const next = new Map(prev);
        const node = next.get(data.node_id);
        if (node) {
          node.status = 'completed';
          node.durationMs = data.duration_ms;
        }
        return next;
      });
    });

    es.addEventListener('node_failed', (e) => {
      const data = JSON.parse(e.data) as { node_id: string; error?: string };
      setNodeStates((prev) => {
        const next = new Map(prev);
        const node = next.get(data.node_id);
        if (node) {
          node.status = 'failed';
          node.error = data.error;
        }
        return next;
      });
    });

    es.addEventListener('run_completed', () => { setRunStatus('completed'); es.close(); });
    es.addEventListener('run_failed', () => { setRunStatus('failed'); es.close(); });
    es.onerror = () => { setRunStatus('failed'); es.close(); };

    return () => es.close();
  }, [pipelineId, runId]);

  return { nodeStates, runStatus };
}
