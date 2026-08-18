import { useState, useRef } from 'react';
import { X, Download, Upload, Copy, Check } from 'lucide-react';
import { usePipelineEditorStore } from '../../stores/pipeline-editor.store';

interface WorkflowShareDialogProps {
  onClose: () => void;
}

export function WorkflowShareDialog({ onClose }: WorkflowShareDialogProps) {
  const { nodes, edges, loadPipeline, pipelineType } = usePipelineEditorStore();
  const [mode, setMode] = useState<'export' | 'import'>('export');
  const [importJson, setImportJson] = useState('');
  const [importError, setImportError] = useState('');
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const workflowJson = JSON.stringify({ version: 1, pipelineType, nodes, edges }, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(workflowJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([workflowJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pipeline-workflow.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = () => {
    setImportError('');
    try {
      const data = JSON.parse(importJson);
      if (!data.nodes || !Array.isArray(data.nodes)) throw new Error('Missing nodes array');
      if (!data.edges || !Array.isArray(data.edges)) throw new Error('Missing edges array');
      loadPipeline(data.nodes, data.edges, data.pipelineType ?? 'ingestion');
      onClose();
    } catch (e) {
      setImportError(e instanceof Error ? e.message : 'Invalid JSON');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setImportJson(reader.result as string);
    };
    reader.readAsText(file);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="w-[560px] max-h-[80vh] bg-surface-800 border border-border-secondary rounded-2xl shadow-2xl overflow-hidden animate-scale-in" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border-primary">
          <h3 className="text-sm font-semibold text-text-primary">Share Workflow</h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary"><X className="w-4 h-4" /></button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border-primary">
          <button
            onClick={() => setMode('export')}
            className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${mode === 'export' ? 'text-accent-400 border-b-2 border-accent-500' : 'text-text-muted hover:text-text-secondary'}`}
          >
            <Download className="w-3 h-3 inline mr-1.5" />Export
          </button>
          <button
            onClick={() => setMode('import')}
            className={`flex-1 px-4 py-2 text-xs font-medium transition-colors ${mode === 'import' ? 'text-accent-400 border-b-2 border-accent-500' : 'text-text-muted hover:text-text-secondary'}`}
          >
            <Upload className="w-3 h-3 inline mr-1.5" />Import
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          {mode === 'export' ? (
            <>
              <p className="text-xs text-text-muted mb-3">
                Export this pipeline as a shareable JSON workflow. Contains {nodes.length} nodes and {edges.length} edges.
              </p>
              <textarea
                readOnly
                value={workflowJson}
                className="w-full h-48 bg-surface-900 border border-border-primary rounded-lg p-3 font-mono text-[10px] text-text-secondary resize-none outline-none"
              />
              <div className="flex gap-2 mt-3">
                <button onClick={handleCopy} className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 rounded-lg text-xs text-text-primary transition-colors">
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  {copied ? 'Copied!' : 'Copy JSON'}
                </button>
                <button onClick={handleDownload} className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-500 hover:bg-accent-600 rounded-lg text-xs text-white transition-colors">
                  <Download className="w-3 h-3" />Download .json
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-xs text-text-muted mb-3">
                Paste a workflow JSON below or upload a .json file. This will replace the current pipeline.
              </p>
              <textarea
                value={importJson}
                onChange={e => setImportJson(e.target.value)}
                placeholder='{"version": 1, "nodes": [...], "edges": [...]}'
                className="w-full h-40 bg-surface-900 border border-border-primary rounded-lg p-3 font-mono text-[10px] text-text-secondary resize-none outline-none placeholder:text-text-muted/40"
              />
              {importError && (
                <p className="text-[10px] text-red-400 mt-1">{importError}</p>
              )}
              <div className="flex gap-2 mt-3">
                <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-700 hover:bg-surface-600 rounded-lg text-xs text-text-primary transition-colors">
                  <Upload className="w-3 h-3" />Upload File
                </button>
                <input ref={fileInputRef} type="file" accept=".json" onChange={handleFileUpload} className="hidden" />
                <button
                  onClick={handleImport}
                  disabled={!importJson.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-500 hover:bg-accent-600 disabled:opacity-50 rounded-lg text-xs text-white transition-colors"
                >
                  Import
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
