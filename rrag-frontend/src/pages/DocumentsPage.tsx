import { useEffect, useState, useRef, useCallback } from 'react';
import { ingestionApi, type IngestionDocument } from '../api/ingestion';
import { Upload, Trash2, X, CloudUpload } from 'lucide-react';

const ALLOWED_EXTENSIONS = new Set([
  '.pdf', '.txt', '.md', '.csv', '.json', '.jsonl',
  '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.html', '.htm', '.xml', '.yaml', '.yml',
]);

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

function validateFiles(files: File[]): string | null {
  for (const file of files) {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      return `Unsupported file type: ${ext} (${file.name})`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large: ${file.name} (${Math.round(file.size / 1024 / 1024)} MB, max 100 MB)`;
    }
  }
  return null;
}

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function DocumentsPage() {
  const [documents, setDocuments] = useState<IngestionDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [hasFiles, setHasFiles] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      const { data } = await ingestionApi.listDocuments();
      setDocuments(Array.isArray(data?.documents) ? data.documents : []);
      setError('');
    } catch (err) {
      setError(`Failed to load documents: ${getErrorMessage(err)}`);
    }
  };

  useEffect(() => { load(); }, []);

  const uploadFiles = useCallback(async (fileList: File[]) => {
    const validationError = validateFiles(fileList);
    if (validationError) {
      setError(validationError);
      return;
    }

    setUploading(true);
    setError('');
    try {
      await ingestionApi.uploadDocuments(fileList);
      if (fileRef.current) fileRef.current.value = '';
      setHasFiles(false);
      await load();
    } catch (err) {
      setError(`Upload failed: ${getErrorMessage(err)}`);
    } finally {
      setUploading(false);
    }
  }, []);

  const handleUpload = async () => {
    const files = fileRef.current?.files;
    if (!files?.length) return;
    await uploadFiles(Array.from(files));
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) uploadFiles(files);
  }, [uploadFiles]);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this document?')) return;
    setError('');
    try {
      await ingestionApi.deleteDocument(id);
      setDocuments((d) => d.filter((doc) => doc.id !== id));
    } catch (err) {
      setError(`Delete failed: ${getErrorMessage(err)}`);
    }
  };

  return (
    <div className="animate-fade-in">
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-500 hover:text-red-300 ml-2">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {documents.length === 0 ? (
        /* ── Empty state: prominent CTA drop zone ── */
        <div className="animate-slide-up">
          <h1 className="text-xl font-bold text-text-primary mb-6">Documents</h1>
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => fileRef.current?.click()}
            className={`relative cursor-pointer rounded-2xl border-2 border-dashed transition-all duration-200 py-20 px-8 text-center ${
              dragOver
                ? 'border-accent-400 bg-accent-500/10 shadow-lg shadow-accent-500/10'
                : 'border-border-secondary bg-surface-800/50 hover:border-accent-500/50 hover:bg-surface-800'
            }`}
          >
            <div className={`mx-auto mb-5 w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${
              dragOver ? 'bg-accent-500/20' : 'bg-surface-700'
            }`}>
              <CloudUpload className={`w-8 h-8 transition-colors ${dragOver ? 'text-accent-400' : 'text-text-muted'}`} />
            </div>
            <h2 className="text-lg font-semibold text-text-primary mb-2">
              Upload your documents
            </h2>
            <p className="text-sm text-text-muted mb-6 max-w-md mx-auto">
              Drag and drop files here, or click to browse. Supported formats: PDF, TXT, Markdown, CSV, JSON, DOCX, XLSX, HTML, YAML.
            </p>
            <div className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-xl hover:from-accent-400 hover:to-accent-500 transition-all shadow-lg shadow-accent-500/20">
              <Upload className="w-4 h-4" />
              Choose Files
            </div>
            <p className="text-xs text-text-muted/60 mt-4">Max 100 MB per file</p>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={Array.from(ALLOWED_EXTENSIONS).join(',')}
              onChange={(e) => {
                const files = e.target.files;
                if (files?.length) uploadFiles(Array.from(files));
              }}
              className="hidden"
            />
            {uploading && (
              <div className="absolute inset-0 bg-surface-900/80 rounded-2xl flex items-center justify-center">
                <div className="flex items-center gap-3 text-accent-400">
                  <div className="w-5 h-5 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-medium">Uploading...</span>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ── Documents list with header upload controls ── */
        <>
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-xl font-bold text-text-primary">Documents</h1>
            <div className="flex items-center gap-3">
              <input
                ref={fileRef}
                type="file"
                multiple
                accept={Array.from(ALLOWED_EXTENSIONS).join(',')}
                onChange={() => setHasFiles(Boolean(fileRef.current?.files?.length))}
                className="text-sm text-text-secondary file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-surface-700 file:text-text-primary hover:file:bg-surface-600 file:cursor-pointer file:transition-colors"
              />
              <button
                onClick={handleUpload}
                disabled={uploading || !hasFiles}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                  hasFiles
                    ? 'bg-gradient-to-r from-accent-500 to-accent-600 text-white hover:from-accent-400 hover:to-accent-500 shadow-lg shadow-accent-500/20'
                    : 'bg-surface-700 text-text-muted cursor-not-allowed'
                } disabled:opacity-50`}
              >
                <Upload className="w-4 h-4" />
                {uploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
          <div className="bg-surface-800 rounded-xl border border-border-primary overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface-900 border-b border-border-primary">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Filename</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Size</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className="border-b border-border-primary last:border-0 hover:bg-surface-700/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-text-primary">{doc.filename}</td>
                    <td className="px-4 py-3 text-text-muted">{doc.content_type}</td>
                    <td className="px-4 py-3 text-text-muted">
                      {doc.metadata.size_bytes ? `${Math.round(Number(doc.metadata.size_bytes) / 1024)} KB` : '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 text-sm transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
