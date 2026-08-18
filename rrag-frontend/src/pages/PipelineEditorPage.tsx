import { ReactFlowProvider } from '@xyflow/react';
import { PipelineToolbar } from '../components/pipeline/PipelineToolbar';
import { ComponentPalette } from '../components/pipeline/ComponentPalette';
import { PipelineCanvas } from '../components/pipeline/PipelineCanvas';
import { PropertyInspector } from '../components/pipeline/PropertyInspector';
import { YamlEditor } from '../components/pipeline/YamlEditor';
import { RunOutputPanel } from '../components/pipeline/RunOutputPanel';
import { usePipelineEditor } from '../hooks/usePipelineEditor';
import { AlertTriangle, Database } from 'lucide-react';

export function PipelineEditorPage() {
  const { loadError, pipelineType, datastoreId } = usePipelineEditor();

  if (loadError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-3 animate-fade-in">
          <AlertTriangle className="w-10 h-10 mx-auto text-red-400" />
          <div className="text-red-400 text-lg font-medium">Failed to load pipeline</div>
          <p className="text-sm text-text-muted">{loadError}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-sm text-accent-400 hover:text-accent-300 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full -m-6">
      <PipelineToolbar />
      {pipelineType === 'query' && datastoreId && (
        <div className="h-8 bg-surface-800 border-b border-border-primary flex items-center px-4 gap-2 text-xs text-text-muted">
          <Database className="w-3.5 h-3.5 text-accent-400" />
          <span>Query Pipeline</span>
          <span className="text-text-muted/50">|</span>
          <span>DataStore: <span className="text-text-secondary font-mono">{datastoreId.slice(0, 8)}...</span></span>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <div className="w-56 border-r border-border-primary overflow-y-auto bg-surface-900">
          <ComponentPalette pipelineType={pipelineType} />
        </div>
        <div className="flex-1 flex flex-col">
          <div className="flex-1">
            <ReactFlowProvider><PipelineCanvas /></ReactFlowProvider>
          </div>
          <div className="h-48 border-t border-border-primary">
            <RunOutputPanel />
          </div>
        </div>
        <div className="w-80 border-l border-border-primary flex flex-col bg-surface-900">
          <div className="flex-1 overflow-y-auto">
            <PropertyInspector />
          </div>
          <div className="h-64 border-t border-border-primary">
            <YamlEditor />
          </div>
        </div>
      </div>
    </div>
  );
}
