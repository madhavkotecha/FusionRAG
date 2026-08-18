import { useEffect, useState, useCallback } from 'react';
import {
  Settings,
  Save,
  RefreshCw,
  Cpu,
  Database,
  HardDrive,
  Layers,
  AlertTriangle,
  CheckCircle,
  X,
  Info,
  Eye,
  EyeOff,
  Globe,
  Server,
  Zap,
} from 'lucide-react';
import client from '../../api/client';

interface SystemConfig {
  llm: {
    defaultModel: string;
    hasApiKey: boolean;
    provider: 'openai' | 'ollama' | 'vllm';
    openaiBaseUrl: string;
    ollamaBaseUrl: string;
    apiKeyDisplay: string;
    vllmBaseUrl: string;
    vllmApiKeyDisplay: string;
  };
  embedding: {
    defaultModel: string;
  };
  queue: {
    name: string;
    jobTimeout: number;
    redisUrl: string;
  };
  storage: {
    storageDir: string;
    configsDir: string;
    maxUploadSizeMb: number;
  };
}

const OPENAI_LLM_MODELS = [
  'gpt-4o-mini',
  'gpt-4o',
  'gpt-4-turbo',
  'gpt-3.5-turbo',
  'claude-3-5-sonnet-20241022',
  'claude-3-haiku-20240307',
];

const OLLAMA_LLM_MODELS = [
  'llama3.2',
  'llama3.1',
  'mistral',
  'gemma2',
  'qwen2.5',
  'deepseek-r1',
];

const OPENAI_EMBEDDING_MODELS = [
  'text-embedding-3-small',
  'text-embedding-3-large',
  'text-embedding-ada-002',
];

const OLLAMA_EMBEDDING_MODELS = [
  'nomic-embed-text',
  'mxbai-embed-large',
  'all-minilm',
];

const VLLM_LLM_MODELS = [
  'Qwen/Qwen3.5-9B',
  'meta-llama/Llama-3.1-8B-Instruct',
  'mistralai/Mistral-7B-Instruct-v0.3',
  'google/gemma-2-9b-it',
  'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B',
];

const VLLM_EMBEDDING_MODELS = [
  'BAAI/bge-large-en-v1.5',
  'intfloat/e5-large-v2',
  'sentence-transformers/all-MiniLM-L6-v2',
];

export function SystemSettingsPage() {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Editable fields
  const [provider, setProvider] = useState<'openai' | 'ollama' | 'vllm'>('openai');
  const [llmModel, setLlmModel] = useState('');
  const [embeddingModel, setEmbeddingModel] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState('');
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState('');
  const [vllmBaseUrl, setVllmBaseUrl] = useState('');
  const [vllmApiKey, setVllmApiKey] = useState('');
  const [showVllmApiKey, setShowVllmApiKey] = useState(false);
  const [jobTimeout, setJobTimeout] = useState(3600);
  const [maxUpload, setMaxUpload] = useState(100);
  const [dirty, setDirty] = useState(false);

  const llmModels = provider === 'openai' ? OPENAI_LLM_MODELS : provider === 'vllm' ? VLLM_LLM_MODELS : OLLAMA_LLM_MODELS;
  const embeddingModels = provider === 'openai' ? OPENAI_EMBEDDING_MODELS : provider === 'vllm' ? VLLM_EMBEDDING_MODELS : OLLAMA_EMBEDDING_MODELS;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get<SystemConfig>('/api/v1/ingestion/admin/config');
      setConfig(data);
      setProvider(data.llm.provider || 'openai');
      setLlmModel(data.llm.defaultModel);
      setEmbeddingModel(data.embedding.defaultModel);
      setOpenaiBaseUrl(data.llm.openaiBaseUrl || '');
      setOllamaBaseUrl(data.llm.ollamaBaseUrl || '');
      setVllmBaseUrl(data.llm.vllmBaseUrl || '');
      setOpenaiApiKey('');
      setVllmApiKey('');
      setShowApiKey(false);
      setJobTimeout(data.queue.jobTimeout);
      setMaxUpload(data.storage.maxUploadSizeMb);
      setDirty(false);
      setError('');
    } catch {
      setError('Failed to load system configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleProviderChange = (newProvider: 'openai' | 'ollama' | 'vllm') => {
    setProvider(newProvider);
    const newLlmModels = newProvider === 'openai' ? OPENAI_LLM_MODELS : newProvider === 'vllm' ? VLLM_LLM_MODELS : OLLAMA_LLM_MODELS;
    const newEmbModels = newProvider === 'openai' ? OPENAI_EMBEDDING_MODELS : newProvider === 'vllm' ? VLLM_EMBEDDING_MODELS : OLLAMA_EMBEDDING_MODELS;
    if (!newLlmModels.includes(llmModel)) {
      setLlmModel(newLlmModels[0]);
    }
    if (!newEmbModels.includes(embeddingModel)) {
      setEmbeddingModel(newEmbModels[0]);
    }
    markDirty();
  };

  const handleSave = async () => {
    setSaving(true);
    setSuccess('');
    try {
      const payload: Record<string, unknown> = {
        defaultLlmModel: llmModel,
        defaultEmbeddingModel: embeddingModel,
        rqJobTimeout: jobTimeout,
        maxUploadSizeMb: maxUpload,
        llmProvider: provider,
        openaiBaseUrl: openaiBaseUrl,
        ollamaBaseUrl: ollamaBaseUrl,
        vllmBaseUrl: vllmBaseUrl,
      };
      if (openaiApiKey) {
        payload.openaiApiKey = openaiApiKey;
      }
      if (vllmApiKey) {
        payload.vllmApiKey = vllmApiKey;
      }
      await client.put('/api/v1/ingestion/admin/config', payload);
      setSuccess('Configuration saved successfully');
      setOpenaiApiKey('');
      setDirty(false);
      await load();
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const markDirty = () => setDirty(true);

  const inputClass = 'w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500';
  const labelClass = 'block text-sm font-medium text-text-secondary mb-1.5';
  const hintClass = 'text-xs text-text-muted mt-1';

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Settings className="w-5 h-5 text-accent-400" />
            System Settings
          </h1>
          <p className="text-sm text-text-muted mt-0.5">Configure platform defaults and resource limits</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-surface-800 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Reload
          </button>
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4" />{error}</div>
          <button onClick={() => setError('')}><X className="w-4 h-4" /></button>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-sm text-emerald-400 flex items-center gap-2 animate-scale-in">
          <CheckCircle className="w-4 h-4" />
          {success}
        </div>
      )}

      {loading && !config ? (
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-surface-800 rounded-xl border border-border-primary p-6 animate-pulse">
              <div className="h-5 bg-surface-700 rounded w-40 mb-4" />
              <div className="h-10 bg-surface-700 rounded w-full" />
            </div>
          ))}
        </div>
      ) : config ? (
        <div className="space-y-6">
          {/* LLM Configuration */}
          <div className="bg-surface-800 rounded-xl border border-border-primary p-6 animate-slide-up">
            <div className="flex items-center gap-2 mb-4">
              <Cpu className="w-5 h-5 text-violet-400" />
              <h2 className="text-base font-semibold text-text-primary">LLM Configuration</h2>
            </div>

            {/* Provider Selector */}
            <div className="mb-5">
              <label className={labelClass}>Provider</label>
              <div className="flex gap-1 p-1 bg-surface-900 rounded-lg w-fit">
                <button
                  onClick={() => handleProviderChange('openai')}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                    provider === 'openai'
                      ? 'bg-accent-500 text-white shadow-sm'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  OpenAI
                </button>
                <button
                  onClick={() => handleProviderChange('ollama')}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                    provider === 'ollama'
                      ? 'bg-accent-500 text-white shadow-sm'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  <Server className="w-3.5 h-3.5" />
                  Ollama
                </button>
                <button
                  onClick={() => handleProviderChange('vllm')}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                    provider === 'vllm'
                      ? 'bg-accent-500 text-white shadow-sm'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  <Zap className="w-3.5 h-3.5" />
                  vLLM
                </button>
              </div>
              <p className={hintClass}>
                {provider === 'openai'
                  ? 'Use OpenAI API or any OpenAI-compatible server'
                  : provider === 'vllm'
                  ? 'Use vLLM for high-throughput GPU inference (OpenAI-compatible API)'
                  : 'Use Ollama for local inference with MPS/GPU acceleration'}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* LLM Model */}
              <div>
                <label className={labelClass}>Default LLM Model</label>
                <select
                  value={llmModel}
                  onChange={(e) => { setLlmModel(e.target.value); markDirty(); }}
                  className={inputClass}
                >
                  {llmModels.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                <p className={hintClass}>Used as default for query pipelines and chat</p>
              </div>

              {/* Provider-specific config */}
              {provider === 'openai' ? (
                <div>
                  <label className={labelClass}>API Key</label>
                  <div className="relative">
                    <input
                      type={showApiKey ? 'text' : 'password'}
                      value={openaiApiKey}
                      onChange={(e) => { setOpenaiApiKey(e.target.value); markDirty(); }}
                      placeholder={config.llm.apiKeyDisplay || 'Enter OpenAI API key'}
                      className={`${inputClass} pr-10 font-mono text-xs`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                    >
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1">
                    {config.llm.hasApiKey ? (
                      <span className="text-xs text-emerald-400 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" /> Key configured
                      </span>
                    ) : (
                      <span className="text-xs text-red-400 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> No key set
                      </span>
                    )}
                  </div>
                </div>
              ) : provider === 'vllm' ? (
                <div>
                  <label className={labelClass}>vLLM Base URL</label>
                  <input
                    type="text"
                    value={vllmBaseUrl}
                    onChange={(e) => { setVllmBaseUrl(e.target.value); markDirty(); }}
                    placeholder="http://host.docker.internal:8100"
                    className={`${inputClass} font-mono text-xs`}
                  />
                  <p className={hintClass}>vLLM server address (use host.docker.internal for host GPU)</p>
                </div>
              ) : (
                <div>
                  <label className={labelClass}>Ollama Base URL</label>
                  <input
                    type="text"
                    value={ollamaBaseUrl}
                    onChange={(e) => { setOllamaBaseUrl(e.target.value); markDirty(); }}
                    placeholder="http://host.docker.internal:11434"
                    className={`${inputClass} font-mono text-xs`}
                  />
                  <p className={hintClass}>Ollama server address (host.docker.internal for host machine)</p>
                </div>
              )}
            </div>

            {/* OpenAI Base URL (shown only for OpenAI provider) */}
            {provider === 'openai' && (
              <div className="mt-4">
                <label className={labelClass}>
                  Base URL <span className="text-text-muted font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={openaiBaseUrl}
                  onChange={(e) => { setOpenaiBaseUrl(e.target.value); markDirty(); }}
                  placeholder="https://api.openai.com/v1 (default)"
                  className={`${inputClass} max-w-lg font-mono text-xs`}
                />
                <p className={hintClass}>For OpenAI-compatible servers: TGI or custom GPU server endpoints</p>
              </div>
            )}

            {/* vLLM API Key (shown only for vLLM provider) */}
            {provider === 'vllm' && (
              <div className="mt-4">
                <label className={labelClass}>
                  API Key <span className="text-text-muted font-normal">(optional — only if vLLM started with --api-key)</span>
                </label>
                <div className="relative max-w-lg">
                  <input
                    type={showVllmApiKey ? 'text' : 'password'}
                    value={vllmApiKey}
                    onChange={(e) => { setVllmApiKey(e.target.value); markDirty(); }}
                    placeholder={config.llm.vllmApiKeyDisplay || 'Not required by default'}
                    className={`${inputClass} pr-10 font-mono text-xs`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowVllmApiKey(!showVllmApiKey)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                  >
                    {showVllmApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Embedding Configuration */}
          <div className="bg-surface-800 rounded-xl border border-border-primary p-6 animate-slide-up" style={{ animationDelay: '50ms' }}>
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-5 h-5 text-highlight-400" />
              <h2 className="text-base font-semibold text-text-primary">Embedding Configuration</h2>
            </div>
            <div>
              <label className={labelClass}>Default Embedding Model</label>
              <select
                value={embeddingModel}
                onChange={(e) => { setEmbeddingModel(e.target.value); markDirty(); }}
                className={`${inputClass} max-w-md`}
              >
                {embeddingModels.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
              <p className={hintClass}>
                Used for document indexing and query embedding
                {provider === 'ollama' && ' (via Ollama)'}
                {provider === 'vllm' && ' (via vLLM)'}
              </p>
            </div>
          </div>

          {/* Queue Configuration */}
          <div className="bg-surface-800 rounded-xl border border-border-primary p-6 animate-slide-up" style={{ animationDelay: '100ms' }}>
            <div className="flex items-center gap-2 mb-4">
              <Layers className="w-5 h-5 text-orange-400" />
              <h2 className="text-base font-semibold text-text-primary">Queue Configuration</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Queue Name</label>
                <input
                  type="text"
                  value={config.queue.name}
                  disabled
                  className="w-full bg-surface-900/50 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-muted"
                />
                <p className={hintClass}>Read-only (set via environment)</p>
              </div>
              <div>
                <label className={labelClass}>Job Timeout (seconds)</label>
                <input
                  type="number"
                  value={jobTimeout}
                  onChange={(e) => { setJobTimeout(parseInt(e.target.value) || 3600); markDirty(); }}
                  min={60}
                  max={86400}
                  className={inputClass}
                />
                <p className={hintClass}>Maximum execution time per job</p>
              </div>
              <div>
                <label className={labelClass}>Redis Endpoint</label>
                <input
                  type="text"
                  value={config.queue.redisUrl}
                  disabled
                  className="w-full bg-surface-900/50 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-muted font-mono text-xs"
                />
                <p className={hintClass}>Read-only (set via environment)</p>
              </div>
            </div>
          </div>

          {/* Storage Configuration */}
          <div className="bg-surface-800 rounded-xl border border-border-primary p-6 animate-slide-up" style={{ animationDelay: '150ms' }}>
            <div className="flex items-center gap-2 mb-4">
              <HardDrive className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-semibold text-text-primary">Storage Configuration</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Storage Directory</label>
                <input
                  type="text"
                  value={config.storage.storageDir}
                  disabled
                  className="w-full bg-surface-900/50 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-muted font-mono text-xs"
                />
              </div>
              <div>
                <label className={labelClass}>Configs Directory</label>
                <input
                  type="text"
                  value={config.storage.configsDir}
                  disabled
                  className="w-full bg-surface-900/50 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-muted font-mono text-xs"
                />
              </div>
              <div>
                <label className={labelClass}>Max Upload Size (MB)</label>
                <input
                  type="number"
                  value={maxUpload}
                  onChange={(e) => { setMaxUpload(parseInt(e.target.value) || 100); markDirty(); }}
                  min={1}
                  max={1024}
                  className={inputClass}
                />
                <p className={hintClass}>Per-file upload limit</p>
              </div>
            </div>
          </div>

          {/* Info Banner */}
          <div className="bg-accent-500/5 border border-accent-500/20 rounded-xl p-4 text-sm text-text-secondary flex items-start gap-3 animate-slide-up" style={{ animationDelay: '200ms' }}>
            <Info className="w-5 h-5 text-accent-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-text-primary">Runtime Configuration</p>
              <p className="text-xs text-text-muted mt-1">
                Changes take effect immediately for query and chat operations. Ingestion pipeline jobs
                running on the worker use environment variable defaults until the worker is restarted.
                Some settings (Redis URL, storage directories) can only be changed via environment variables.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
