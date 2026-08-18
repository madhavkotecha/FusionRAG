import { useState, useCallback, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { Trash2, AlertCircle, CheckCircle, Code2, Eye, Upload, Loader2, Puzzle } from 'lucide-react';
import client from '../api/client';
import { useAuthStore } from '../stores/auth.store';
import type { ComponentDefinition } from '../types/pipeline';

const DEFAULT_TEMPLATE = `from pipeline_service.framework import component, step, CompositeComponent

@component(
    category="retriever",
    name="My Custom Component",
    description="Describe what this component does",
    input_ports=[{"name": "query", "type": "string"}],
    output_ports=[{"name": "answer", "type": "string"}],
)
class MyCustomComponent(CompositeComponent):
    @step(order=1, name="Step One")
    async def step_one(self, input_data, config):
        # Process input
        return {"result": "processed"}

    @step(order=2, name="Step Two")
    async def step_two(self, input_data, config):
        # Generate output
        return {"answer": "final result"}
`;

interface ParsedMeta {
  name: string | null;
  category: string | null;
  description: string | null;
  isComposite: boolean;
  inputPorts: Array<{ name: string; type: string }>;
  outputPorts: Array<{ name: string; type: string }>;
  steps: Array<{ order: number; name: string }>;
}

function extractMeta(code: string): ParsedMeta {
  const meta: ParsedMeta = {
    name: null,
    category: null,
    description: null,
    isComposite: false,
    inputPorts: [],
    outputPorts: [],
    steps: [],
  };

  // Extract @component decorator arguments
  const componentMatch = code.match(/@component\s*\(([\s\S]*?)\)\s*\nclass/);
  if (!componentMatch) return meta;

  const decoratorBody = componentMatch[1];

  // Extract name
  const nameMatch = decoratorBody.match(/name\s*=\s*["']([^"']+)["']/);
  if (nameMatch) meta.name = nameMatch[1];

  // Extract category
  const catMatch = decoratorBody.match(/category\s*=\s*["']([^"']+)["']/);
  if (catMatch) meta.category = catMatch[1];

  // Extract description
  const descMatch = decoratorBody.match(/description\s*=\s*["']([^"']+)["']/);
  if (!descMatch) {
    // Try multi-line parenthesized string
    const descMulti = decoratorBody.match(/description\s*=\s*\(\s*["']([\s\S]*?)["']\s*\)/);
    if (descMulti) meta.description = descMulti[1].replace(/["']\s*["']/g, '');
  } else {
    meta.description = descMatch[1];
  }

  // Extract input_ports
  const inputMatch = decoratorBody.match(/input_ports\s*=\s*\[([\s\S]*?)\]/);
  if (inputMatch) {
    const portMatches = inputMatch[1].matchAll(/\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"([^"]+)"\s*\}/g);
    for (const pm of portMatches) {
      meta.inputPorts.push({ name: pm[1], type: pm[2] });
    }
  }

  // Extract output_ports
  const outputMatch = decoratorBody.match(/output_ports\s*=\s*\[([\s\S]*?)\]/);
  if (outputMatch) {
    const portMatches = outputMatch[1].matchAll(/\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"type"\s*:\s*"([^"]+)"\s*\}/g);
    for (const pm of portMatches) {
      meta.outputPorts.push({ name: pm[1], type: pm[2] });
    }
  }

  // Check if composite
  meta.isComposite = /class\s+\w+\s*\(\s*CompositeComponent\s*\)/.test(code);

  // Extract @step decorators
  const stepMatches = code.matchAll(/@step\s*\([^)]*order\s*=\s*(\d+)[^)]*name\s*=\s*["']([^"']+)["'][^)]*\)/g);
  for (const sm of stepMatches) {
    meta.steps.push({ order: parseInt(sm[1], 10), name: sm[2] });
  }
  // Also try name before order
  const stepMatches2 = code.matchAll(/@step\s*\([^)]*name\s*=\s*["']([^"']+)["'][^)]*order\s*=\s*(\d+)[^)]*\)/g);
  for (const sm of stepMatches2) {
    if (!meta.steps.find(s => s.name === sm[1])) {
      meta.steps.push({ order: parseInt(sm[2], 10), name: sm[1] });
    }
  }
  meta.steps.sort((a, b) => a.order - b.order);

  return meta;
}

function getErrorMessage(err: unknown): string {
  const axiosErr = err as { response?: { data?: { detail?: string } } };
  const detail = axiosErr?.response?.data?.detail;
  if (detail) return typeof detail === 'string' ? detail : JSON.stringify(detail);
  if (err instanceof Error) return err.message;
  return String(err);
}

export function ComponentCreatorPage() {
  const [code, setCode] = useState(DEFAULT_TEMPLATE);
  const [meta, setMeta] = useState<ParsedMeta>(() => extractMeta(DEFAULT_TEMPLATE));
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [customComponents, setCustomComponents] = useState<ComponentDefinition[]>([]);
  const [loadingComponents, setLoadingComponents] = useState(true);
  const timerRef = useRef<number>(undefined);

  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.orgRole === 'org_admin' || user?.isPlatformAdmin === true;
  const workspaceId = user?.workspaces?.[0]?.workspaceId ?? 'default';

  const fetchCustomComponents = useCallback(async () => {
    setLoadingComponents(true);
    try {
      const { data } = await client.get<ComponentDefinition[]>('/api/v1/components');
      setCustomComponents(data.filter((c) => c.source === 'custom'));
    } catch {
      // silently ignore
    } finally {
      setLoadingComponents(false);
    }
  }, []);

  useEffect(() => {
    fetchCustomComponents();
  }, [fetchCustomComponents]);

  const handleCodeChange = useCallback((value: string | undefined) => {
    if (!value) return;
    setCode(value);
    clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      setMeta(extractMeta(value));
    }, 300);
  }, []);

  const handleRegister = useCallback(async () => {
    setRegistering(true);
    setError(null);
    setSuccess(null);
    try {
      const blob = new Blob([code], { type: 'text/x-python' });
      const file = new File([blob], 'component.py', { type: 'text/x-python' });
      const formData = new FormData();
      formData.append('file', file);
      const resp = await client.post(
        `/api/v1/components/upload?workspace_id=${workspaceId}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setSuccess(`Registered: ${resp.data.name} (${resp.data.type})`);
      fetchCustomComponents();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRegistering(false);
    }
  }, [code, workspaceId, fetchCustomComponents]);

  const handleDelete = useCallback(async (componentType: string) => {
    if (!window.confirm(`Delete custom component "${componentType}"?`)) return;
    try {
      await client.delete(`/api/v1/components/custom/${componentType}?workspace_id=${workspaceId}`);
      fetchCustomComponents();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }, [workspaceId, fetchCustomComponents]);

  return (
    <div className="animate-fade-in h-full flex flex-col">
      {isAdmin && (
        <div className="mb-4 p-3 bg-accent-500/10 border border-accent-500/20 rounded-lg flex items-center justify-between">
          <span className="text-sm text-accent-400">
            You have admin access. View and manage all registered components.
          </span>
          <Link
            to="/admin/components"
            className="text-sm font-medium text-accent-400 hover:text-accent-300 underline"
          >
            Manage all components →
          </Link>
        </div>
      )}
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
            <Puzzle className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-text-primary">Component Creator</h1>
            <p className="text-xs text-text-muted">Write Python code to register custom pipeline components</p>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-3 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-300 text-xs font-medium">Dismiss</button>
        </div>
      )}
      {success && (
        <div className="mb-3 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-sm text-emerald-400 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="ml-auto text-emerald-500 hover:text-emerald-300 text-xs font-medium">Dismiss</button>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Left panel: Code Editor (60%) */}
        <div className="w-[60%] flex flex-col min-h-0">
          <div className="flex items-center gap-2 px-3 py-2 bg-surface-900 border border-border-primary rounded-t-xl border-b-0">
            <Code2 className="w-4 h-4 text-accent-400" />
            <span className="text-sm font-medium text-text-primary">Component Code</span>
            <span className="text-[10px] text-text-muted ml-auto">Python</span>
          </div>
          <div className="flex-1 border border-border-primary rounded-b-xl overflow-hidden">
            <Editor
              height="100%"
              language="python"
              value={code}
              onChange={handleCodeChange}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                wordWrap: 'on',
                scrollBeyondLastLine: false,
                padding: { top: 12 },
                lineNumbers: 'on',
                renderLineHighlight: 'gutter',
                bracketPairColorization: { enabled: true },
              }}
            />
          </div>
        </div>

        {/* Right panel (40%) */}
        <div className="w-[40%] flex flex-col min-h-0 gap-4">
          {/* Preview section */}
          <div className="bg-surface-900 border border-border-primary rounded-xl p-4 shrink-0">
            <div className="flex items-center gap-2 mb-3">
              <Eye className="w-4 h-4 text-highlight-400" />
              <span className="text-sm font-medium text-text-primary">Live Preview</span>
            </div>

            <div className="space-y-3">
              {/* Name + Category */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-[10px] text-text-muted uppercase tracking-wider">Name</label>
                  <div className="text-sm text-text-primary font-medium mt-0.5">
                    {meta.name || <span className="text-text-muted italic">Not detected</span>}
                  </div>
                </div>
                <div className="flex-1">
                  <label className="text-[10px] text-text-muted uppercase tracking-wider">Category</label>
                  <div className="mt-0.5">
                    {meta.category ? (
                      <span className="text-xs px-2 py-0.5 rounded bg-accent-500/10 text-accent-400 border border-accent-500/20">
                        {meta.category}
                      </span>
                    ) : (
                      <span className="text-sm text-text-muted italic">Not detected</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Description */}
              {meta.description && (
                <div>
                  <label className="text-[10px] text-text-muted uppercase tracking-wider">Description</label>
                  <p className="text-xs text-text-secondary mt-0.5">{meta.description}</p>
                </div>
              )}

              {/* Composite badge */}
              {meta.isComposite && (
                <div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 uppercase tracking-wider font-medium">
                    Composite Component
                  </span>
                </div>
              )}

              {/* Ports */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-[10px] text-text-muted uppercase tracking-wider">Input Ports</label>
                  {meta.inputPorts.length > 0 ? (
                    <div className="mt-1 space-y-1">
                      {meta.inputPorts.map((p, i) => (
                        <div key={i} className="text-xs flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          <span className="text-text-primary">{p.name}</span>
                          <span className="text-text-muted">: {p.type}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-text-muted mt-1 italic">None</div>
                  )}
                </div>
                <div className="flex-1">
                  <label className="text-[10px] text-text-muted uppercase tracking-wider">Output Ports</label>
                  {meta.outputPorts.length > 0 ? (
                    <div className="mt-1 space-y-1">
                      {meta.outputPorts.map((p, i) => (
                        <div key={i} className="text-xs flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-orange-400" />
                          <span className="text-text-primary">{p.name}</span>
                          <span className="text-text-muted">: {p.type}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-text-muted mt-1 italic">None</div>
                  )}
                </div>
              </div>

              {/* Steps (if composite) */}
              {meta.steps.length > 0 && (
                <div>
                  <label className="text-[10px] text-text-muted uppercase tracking-wider">Steps</label>
                  <div className="mt-1 space-y-1">
                    {meta.steps.map((s, i) => (
                      <div key={i} className="text-xs flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md bg-surface-800 border border-border-primary flex items-center justify-center text-text-muted text-[10px] font-mono shrink-0">
                          {s.order}
                        </span>
                        <span className="text-text-primary">{s.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Register button */}
            <button
              onClick={handleRegister}
              disabled={registering || !meta.name || !meta.category}
              className="mt-4 w-full flex items-center justify-center gap-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm py-2.5 px-4 rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
            >
              {registering ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Registering...</>
              ) : (
                <><Upload className="w-4 h-4" /> Register Component</>
              )}
            </button>
          </div>

          {/* Custom components list */}
          <div className="flex-1 bg-surface-900 border border-border-primary rounded-xl p-4 overflow-auto min-h-0">
            <div className="flex items-center gap-2 mb-3">
              <Puzzle className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-medium text-text-primary">Registered Components</span>
              <span className="text-[10px] text-text-muted">({customComponents.length})</span>
            </div>

            {loadingComponents ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-text-muted" />
              </div>
            ) : customComponents.length === 0 ? (
              <div className="text-center py-8">
                <Puzzle className="w-8 h-8 mx-auto text-text-muted mb-2 opacity-30" />
                <p className="text-xs text-text-muted">No custom components yet</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {customComponents.map((comp) => (
                  <div
                    key={comp.type}
                    className="flex items-center justify-between p-2.5 bg-surface-800/50 border border-border-primary rounded-lg hover:border-border-hover transition-colors group"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-text-primary font-medium truncate">{comp.name}</span>
                        {comp.isComposite && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 shrink-0">
                            composite
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-text-muted font-mono">{comp.type}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-text-muted">{comp.category}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(comp.type)}
                      className="text-text-muted hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 p-1"
                      title="Delete component"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
