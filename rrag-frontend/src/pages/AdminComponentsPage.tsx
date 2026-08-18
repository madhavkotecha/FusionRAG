import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../stores/auth.store';
import {
  adminComponentsApi,
  type AdminComponent,
  type ComponentCode,
  type ComponentVersion,
  type VersionListResponse,
} from '../api/admin-components';
import Editor from '@monaco-editor/react';
import {
  X,
  Save,
  RotateCcw,
  Code2,
  Info,
  History,
  Search,
  ChevronDown,
} from 'lucide-react';

const CATEGORY_COLORS: Record<string, string> = {
  parser: 'bg-blue-500/20 text-blue-400',
  chunker: 'bg-purple-500/20 text-purple-400',
  embedder: 'bg-cyan-500/20 text-cyan-400',
  extractor: 'bg-yellow-500/20 text-yellow-400',
  indexer: 'bg-green-500/20 text-green-400',
  graph_builder: 'bg-emerald-500/20 text-emerald-400',
  storage: 'bg-teal-500/20 text-teal-400',
  retriever: 'bg-indigo-500/20 text-indigo-400',
  reranker: 'bg-orange-500/20 text-orange-400',
  generator: 'bg-pink-500/20 text-pink-400',
  planner: 'bg-lime-500/20 text-lime-400',
  agent: 'bg-red-500/20 text-red-400',
};

type DrawerTab = 'code' | 'metadata' | 'versions';

export function AdminComponentsPage() {
  const user = useAuthStore((s) => s.user);

  // ── List state ──
  const [components, setComponents] = useState<AdminComponent[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // ── Drawer state ──
  const [selected, setSelected] = useState<AdminComponent | null>(null);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('code');
  const [codeData, setCodeData] = useState<ComponentCode | null>(null);
  const [editedCode, setEditedCode] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState<VersionListResponse | null>(null);
  const [alert, setAlert] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // suppress unused var warning — user may be used for future role checks
  void user;

  // ── Fetch components ──
  const fetchComponents = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (sourceFilter) params.source = sourceFilter;
      if (categoryFilter) params.category = categoryFilter;
      if (searchQuery) params.search = searchQuery;
      const { data } = await adminComponentsApi.list(params);
      setComponents(data);
    } catch {
      setAlert({ type: 'error', message: 'Failed to load components' });
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, categoryFilter, searchQuery]);

  useEffect(() => { fetchComponents(); }, [fetchComponents]);

  // ── Open drawer ──
  const openDrawer = async (comp: AdminComponent) => {
    setSelected(comp);
    setDrawerTab('code');
    setAlert(null);
    try {
      const { data } = await adminComponentsApi.getCode(
        comp.type,
        comp.workspace_id || '_global',
      );
      setCodeData(data);
      setEditedCode(data.code);
    } catch {
      setCodeData(null);
      setEditedCode('');
    }
  };

  const closeDrawer = () => {
    setSelected(null);
    setCodeData(null);
    setEditedCode('');
    setChangeReason('');
    setVersions(null);
  };

  // ── Save code ──
  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await adminComponentsApi.updateCode(
        selected.type,
        editedCode,
        changeReason || undefined,
        selected.workspace_id || '_global',
      );
      setAlert({ type: 'success', message: 'Code saved successfully' });
      setChangeReason('');
      fetchComponents();
      // Refresh code data
      const { data } = await adminComponentsApi.getCode(
        selected.type,
        selected.workspace_id || '_global',
      );
      setCodeData(data);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setAlert({ type: 'error', message: axiosErr.response?.data?.detail || 'Save failed' });
    } finally {
      setSaving(false);
    }
  };

  // ── Load versions ──
  const loadVersions = useCallback(async () => {
    if (!selected) return;
    try {
      const { data } = await adminComponentsApi.listVersions(
        selected.type,
        selected.workspace_id || '_global',
      );
      setVersions(data);
    } catch {
      setVersions(null);
    }
  }, [selected]);

  useEffect(() => {
    if (drawerTab === 'versions' && selected) loadVersions();
  }, [drawerTab, selected, loadVersions]);

  // ── Revert ──
  const handleRevert = async (version: number) => {
    if (!selected) return;
    try {
      await adminComponentsApi.revert(
        selected.type,
        version,
        selected.workspace_id || '_global',
      );
      setAlert({ type: 'success', message: `Reverted to version ${version}` });
      loadVersions();
      // Refresh code
      const { data } = await adminComponentsApi.getCode(
        selected.type,
        selected.workspace_id || '_global',
      );
      setCodeData(data);
      setEditedCode(data.code);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setAlert({ type: 'error', message: axiosErr.response?.data?.detail || 'Revert failed' });
    }
  };

  // ── Unique categories for filter ──
  const categories = [...new Set(components.map((c) => c.category))].sort();

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Manage Components</h1>
        <p className="text-sm text-text-muted mt-1">
          View and edit registered pipeline components
        </p>
      </div>

      {/* Alert */}
      {alert && (
        <div className={`p-3 rounded-lg text-sm flex items-center justify-between ${
          alert.type === 'success' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
        }`}>
          <span>{alert.message}</span>
          <button onClick={() => setAlert(null)} className="ml-2 hover:opacity-80">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Source tabs */}
        <div className="flex bg-surface-800 rounded-lg p-0.5">
          {(['', 'seed', 'custom'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSourceFilter(s)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                sourceFilter === s
                  ? 'bg-accent-500 text-white'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {s === '' ? 'All' : s === 'seed' ? 'Seed' : 'Custom'}
            </button>
          ))}
        </div>

        {/* Category dropdown */}
        <div className="relative">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="appearance-none bg-surface-800 border border-border-primary rounded-lg px-3 py-1.5 pr-8 text-xs text-text-secondary focus:outline-none focus:ring-1 focus:ring-accent-500"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted pointer-events-none" />
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search components..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-surface-800 border border-border-primary rounded-lg pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent-500"
          />
        </div>

        <span className="text-xs text-text-muted ml-auto">{components.length} components</span>
      </div>

      {/* Table */}
      <div className="bg-surface-800 border border-border-primary rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-primary text-left">
              <th className="px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Name</th>
              <th className="px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Type</th>
              <th className="px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Category</th>
              <th className="px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Source</th>
              <th className="px-4 py-3 text-xs font-medium text-text-muted uppercase tracking-wider">Version</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">Loading...</td></tr>
            ) : components.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">No components found</td></tr>
            ) : components.map((comp) => (
              <tr
                key={`${comp.type}-${comp.workspace_id}`}
                onClick={() => openDrawer(comp)}
                className="border-b border-border-primary/50 hover:bg-surface-700/50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 font-medium text-text-primary">{comp.name}</td>
                <td className="px-4 py-3 text-text-secondary font-mono text-xs">{comp.type}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_COLORS[comp.category] || 'bg-gray-500/20 text-gray-400'}`}>
                    {comp.category}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    comp.source === 'seed' ? 'bg-amber-500/20 text-amber-400' : 'bg-sky-500/20 text-sky-400'
                  }`}>
                    {comp.source}
                  </span>
                </td>
                <td className="px-4 py-3 text-text-muted text-xs">v{comp.current_version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Side Drawer */}
      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={closeDrawer} />
          <div className="relative w-[700px] max-w-full bg-surface-900 border-l border-border-primary flex flex-col animate-slide-in-right">
            {/* Drawer Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-primary">
              <div>
                <h2 className="text-lg font-semibold text-text-primary">{selected.name}</h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_COLORS[selected.category] || 'bg-gray-500/20 text-gray-400'}`}>
                    {selected.category}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    selected.source === 'seed' ? 'bg-amber-500/20 text-amber-400' : 'bg-sky-500/20 text-sky-400'
                  }`}>
                    {selected.source}
                  </span>
                  <span className="text-xs text-text-muted">
                    {selected.workspace_id ? `Workspace: ${selected.workspace_id}` : 'Global'}
                  </span>
                </div>
              </div>
              <button onClick={closeDrawer} className="p-1 rounded hover:bg-surface-800">
                <X className="w-5 h-5 text-text-muted" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-border-primary">
              {([
                { key: 'code' as const, icon: Code2, label: 'Code' },
                { key: 'metadata' as const, icon: Info, label: 'Metadata' },
                { key: 'versions' as const, icon: History, label: 'Versions' },
              ]).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setDrawerTab(tab.key)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                    drawerTab === tab.key
                      ? 'border-accent-500 text-accent-400'
                      : 'border-transparent text-text-muted hover:text-text-primary'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto">
              {/* Code Tab */}
              {drawerTab === 'code' && (
                <div className="flex flex-col h-full">
                  <div className="flex-1 min-h-0" style={{ height: '500px' }}>
                    <Editor
                      height="100%"
                      language="python"
                      theme="vs-dark"
                      value={editedCode}
                      onChange={(val) => setEditedCode(val || '')}
                      options={{
                        readOnly: !codeData?.can_edit,
                        minimap: { enabled: false },
                        fontSize: 13,
                        lineNumbers: 'on',
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                      }}
                    />
                  </div>
                  {codeData?.can_edit && (
                    <div className="border-t border-border-primary p-3 flex items-center gap-3">
                      <input
                        type="text"
                        placeholder="Change reason (optional)"
                        value={changeReason}
                        onChange={(e) => setChangeReason(e.target.value)}
                        className="flex-1 bg-surface-800 border border-border-primary rounded-lg px-3 py-1.5 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent-500"
                      />
                      <button
                        onClick={handleSave}
                        disabled={saving || editedCode === codeData?.code}
                        className="flex items-center gap-1.5 px-4 py-1.5 bg-accent-500 text-white text-xs font-medium rounded-lg hover:bg-accent-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        <Save className="w-3.5 h-3.5" />
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  )}
                  {codeData && !codeData.can_edit && (
                    <div className="border-t border-border-primary p-3">
                      <p className="text-xs text-text-muted">Read-only — you do not have permission to edit this component.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Metadata Tab */}
              {drawerTab === 'metadata' && (
                <div className="p-5 space-y-5">
                  <div>
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Description</h3>
                    <p className="text-sm text-text-secondary">{selected.description || 'No description'}</p>
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Input Ports</h3>
                    {selected.input_ports.length === 0 ? (
                      <p className="text-xs text-text-muted">None (source component)</p>
                    ) : (
                      <div className="space-y-1">
                        {selected.input_ports.map((p, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="w-2 h-2 rounded-full bg-blue-400" />
                            <span className="text-text-primary font-medium">{p.name}</span>
                            <span className="text-text-muted">({p.type})</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Output Ports</h3>
                    <div className="space-y-1">
                      {selected.output_ports.map((p, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className="w-2 h-2 rounded-full bg-green-400" />
                          <span className="text-text-primary font-medium">{p.name}</span>
                          <span className="text-text-muted">({p.type})</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Config Schema</h3>
                    <pre className="bg-surface-800 rounded-lg p-3 text-xs text-text-secondary overflow-x-auto max-h-80">
                      {JSON.stringify(selected.config_schema, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* Versions Tab */}
              {drawerTab === 'versions' && (
                <div className="p-5">
                  {!versions ? (
                    <p className="text-sm text-text-muted">Loading versions...</p>
                  ) : versions.items.length === 0 ? (
                    <p className="text-sm text-text-muted">No version history available</p>
                  ) : (
                    <div className="space-y-3">
                      {versions.items.map((v: ComponentVersion) => (
                        <div
                          key={v.id}
                          className="bg-surface-800 rounded-lg p-3 border border-border-primary"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-text-primary">
                                v{v.version}
                              </span>
                              {v.version === codeData?.current_version && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-500/20 text-green-400">
                                  current
                                </span>
                              )}
                            </div>
                            {codeData?.can_edit && v.version !== codeData?.current_version && (
                              <button
                                onClick={() => handleRevert(v.version)}
                                className="flex items-center gap-1 px-2 py-1 text-xs text-orange-400 hover:bg-orange-500/10 rounded transition-colors"
                              >
                                <RotateCcw className="w-3 h-3" />
                                Revert
                              </button>
                            )}
                          </div>
                          <div className="mt-1 text-xs text-text-muted">
                            <span>{v.changed_by}</span>
                            <span className="mx-1.5">&middot;</span>
                            <span>{new Date(v.created_at).toLocaleString()}</span>
                          </div>
                          {v.change_reason && (
                            <p className="mt-1 text-xs text-text-secondary">{v.change_reason}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
