import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { usePipelineEditorStore } from '../../stores/pipeline-editor.store';
import { pipelineApi } from '../../api/pipelines';
import { queryPipelineApi } from '../../api/chat';
import { Save, Play, Download, Upload, X, AlertCircle, CheckCircle, Rocket } from 'lucide-react';

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function PipelineToolbar() {
  const { id } = useParams<{ id: string }>();
  const { nodes, edges, isDirty, yamlSource, queryPipelineId } = usePipelineEditorStore();
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [published, setPublished] = useState(false);

  const handleSave = async () => {
    if (!id) return;
    setSaving(true);
    setError(null);
    try {
      if (queryPipelineId) {
        await queryPipelineApi.update(queryPipelineId, {
          definition: { nodes, edges },
        });
      } else {
        await pipelineApi.update(id, {
          definition: { nodes, edges },
        } as never);
      }
      usePipelineEditorStore.setState({ isDirty: false });
    } catch (err) {
      setError(`Save failed: ${getErrorMessage(err)}`);
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!id) return;
    setPublishing(true);
    setError(null);
    try {
      // Save first if dirty
      if (isDirty) {
        if (queryPipelineId) {
          await queryPipelineApi.update(queryPipelineId, { definition: { nodes, edges } });
        } else {
          await pipelineApi.update(id, { definition: { nodes, edges } } as never);
        }
        usePipelineEditorStore.setState({ isDirty: false });
      }
      // Then update status to published
      if (!queryPipelineId) {
        await pipelineApi.update(id, { status: 'published' } as never);
      }
      setPublished(true);
      setTimeout(() => setPublished(false), 3000);
    } catch (err) {
      setError(`Publish failed: ${getErrorMessage(err)}`);
    } finally {
      setPublishing(false);
    }
  };

  const handleRun = async () => {
    if (!id) return;
    setRunning(true);
    setError(null);
    try {
      const { data } = await pipelineApi.run(id);
      setLastRunId(data.id);
    } catch (err) {
      setError(`Run failed: ${getErrorMessage(err)}`);
    } finally {
      setRunning(false);
    }
  };

  const handleExportYaml = () => {
    const blob = new Blob([yamlSource], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pipeline.yaml';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportYaml = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.yaml,.yml';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const text = await file.text();
      usePipelineEditorStore.getState().syncFromYaml(text);
    };
    input.click();
  };

  return (
    <div className="h-12 bg-surface-900 border-b border-border-primary flex items-center px-4 gap-2">
      <button
        onClick={handleSave}
        disabled={saving || !isDirty}
        className="flex items-center gap-1.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm py-1.5 px-4 rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        <Save className="w-3.5 h-3.5" />
        {saving ? 'Saving...' : 'Save'}
      </button>
      <button
        onClick={handlePublish}
        disabled={publishing || published}
        className={`flex items-center gap-1.5 text-sm py-1.5 px-4 rounded-lg transition-all disabled:cursor-not-allowed ${
          published
            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            : 'bg-gradient-to-r from-violet-600 to-violet-500 text-white hover:from-violet-500 hover:to-violet-400 disabled:opacity-40'
        }`}
      >
        {published ? <CheckCircle className="w-3.5 h-3.5" /> : <Rocket className="w-3.5 h-3.5" />}
        {publishing ? 'Publishing...' : published ? 'Published' : 'Publish'}
      </button>
      <button
        onClick={handleRun}
        disabled={running}
        className="flex items-center gap-1.5 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm py-1.5 px-4 rounded-lg hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        <Play className="w-3.5 h-3.5" />
        {running ? 'Running...' : 'Run'}
      </button>
      <div className="w-px h-6 bg-border-primary mx-1" />
      <button
        onClick={handleExportYaml}
        className="flex items-center gap-1.5 text-text-secondary text-sm py-1.5 px-3 rounded-lg hover:bg-surface-800 hover:text-text-primary border border-border-primary transition-colors"
      >
        <Download className="w-3.5 h-3.5" />
        Export
      </button>
      <button
        onClick={handleImportYaml}
        className="flex items-center gap-1.5 text-text-secondary text-sm py-1.5 px-3 rounded-lg hover:bg-surface-800 hover:text-text-primary border border-border-primary transition-colors"
      >
        <Upload className="w-3.5 h-3.5" />
        Import
      </button>
      {error && (
        <span className="text-xs text-red-400 ml-2 flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5" />
          {error}
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300">
            <X className="w-3 h-3" />
          </button>
        </span>
      )}
      {isDirty && !error && (
        <span className="flex items-center gap-1.5 text-xs text-amber-400 ml-2">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse-glow" />
          Unsaved changes
        </span>
      )}
      {lastRunId && (
        <span className="text-xs text-text-muted ml-auto font-mono">
          Last run: {lastRunId.slice(0, 8)}...
        </span>
      )}
    </div>
  );
}
