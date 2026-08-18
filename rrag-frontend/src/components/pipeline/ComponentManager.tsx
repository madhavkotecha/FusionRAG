import { useState, useCallback } from 'react';
import { Upload, Trash2, AlertCircle, CheckCircle } from 'lucide-react';
import client from '../../api/client';
import type { ComponentDefinition } from '../../types/pipeline';

interface ComponentManagerProps {
  workspaceId: string;
  customComponents: ComponentDefinition[];
  onComponentRegistered: () => void;
}

export function ComponentManager({ workspaceId, customComponents, onComponentRegistered }: ComponentManagerProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.endsWith('.py')) { setError('Only .py files accepted'); return; }
    setUploading(true); setError(null); setSuccess(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const resp = await client.post(`/api/v1/components/upload?workspace_id=${workspaceId}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSuccess(`Registered: ${resp.data.name} (${resp.data.type})`);
      onComponentRegistered();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      const detail = axiosErr.response?.data?.detail || 'Upload failed';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally { setUploading(false); }
  }, [workspaceId, onComponentRegistered]);

  const handleDelete = useCallback(async (componentType: string) => {
    try {
      await client.delete(`/api/v1/components/custom/${componentType}?workspace_id=${workspaceId}`);
      onComponentRegistered();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Delete failed');
    }
  }, [workspaceId, onComponentRegistered]);

  return (
    <div className="border-t border-gray-800 mt-2 pt-2">
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2 mb-2">Custom Components</h4>
      {customComponents.map((comp) => (
        <div key={comp.type} className="flex items-center justify-between px-2 py-1 text-xs text-gray-300 hover:bg-gray-800 rounded">
          <span>{comp.name}{comp.isComposite && <span className="ml-1 text-purple-400 text-[10px]">composite</span>}</span>
          <button onClick={() => handleDelete(comp.type)} className="text-gray-500 hover:text-red-400" title="Remove"><Trash2 size={12} /></button>
        </div>
      ))}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const file = e.dataTransfer.files[0]; if (file) handleUpload(file); }}
        className="mx-2 mt-2 p-3 border border-dashed border-gray-700 rounded text-center text-xs text-gray-500 hover:border-gray-500 cursor-pointer"
        onClick={() => { const input = document.createElement('input'); input.type = 'file'; input.accept = '.py'; input.onchange = (e) => { const file = (e.target as HTMLInputElement).files?.[0]; if (file) handleUpload(file); }; input.click(); }}
      >
        <Upload size={16} className="mx-auto mb-1" />
        {uploading ? 'Uploading...' : 'Drop .py file or click'}
      </div>
      {error && <div className="mx-2 mt-1 flex items-center gap-1 text-xs text-red-400"><AlertCircle size={12} /> {error}</div>}
      {success && <div className="mx-2 mt-1 flex items-center gap-1 text-xs text-green-400"><CheckCircle size={12} /> {success}</div>}
    </div>
  );
}
