import { useEffect, useState } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { usePipelineEditorStore } from '../stores/pipeline-editor.store';
import { pipelineApi } from '../api/pipelines';
import { queryPipelineApi } from '../api/chat';
import { queryPipelineToNodes } from '../lib/query-pipeline-to-nodes';
import type { PipelineNodeData, PipelineType } from '../types/pipeline';
import type { Node, Edge } from '@xyflow/react';

export function usePipelineEditor() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const isQueryPipeline = location.pathname.startsWith('/query-pipelines/');
  const { loadPipeline, clear, nodes, edges, isDirty, pipelineType, datastoreId, queryPipelineId } =
    usePipelineEditorStore();
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    let cancelled = false;

    const fetchPipeline = async () => {
      try {
        if (isQueryPipeline) {
          // Load from ingestion service query pipeline API
          const { data } = await queryPipelineApi.get(id);
          if (cancelled) return;

          const defn = (data.definition as { nodes?: unknown[]; edges?: unknown[] }) || {};
          let pipelineNodes = (defn.nodes || []) as Node<PipelineNodeData>[];
          let pipelineEdges = (defn.edges || []) as Edge[];

          // If no visual definition exists, generate nodes from the structured config
          if (pipelineNodes.length === 0) {
            const generated = queryPipelineToNodes(data);
            pipelineNodes = generated.nodes;
            pipelineEdges = generated.edges;
          }

          loadPipeline(pipelineNodes, pipelineEdges, 'query', data.datastore_id, id);
        } else {
          // Load from pipeline service
          const { data } = await pipelineApi.get(id);
          if (cancelled) return;
          const pipelineNodes = (data.definition?.nodes || []) as Node<PipelineNodeData>[];
          const pipelineEdges = (data.definition?.edges || []) as Edge[];
          loadPipeline(
            pipelineNodes,
            pipelineEdges,
            data.pipelineType as PipelineType,
            data.datastoreId,
          );
        }
        setLoadError(null);
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setLoadError(`Failed to load pipeline: ${msg}`);
      }
    };

    fetchPipeline();

    return () => {
      cancelled = true;
      clear();
    };
  }, [id, isQueryPipeline, loadPipeline, clear]);

  return { nodes, edges, isDirty, loadError, pipelineType, datastoreId, queryPipelineId };
}
