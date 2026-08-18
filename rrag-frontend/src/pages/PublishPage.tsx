import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ingestionApi, type DataStore } from '../api/ingestion';
import { queryPipelineApi, type QueryPipeline } from '../api/chat';
import client from '../api/client';
import {
  Rocket,
  Loader2,
  Database,
  Search,
  Settings2,
  CheckCircle2,
  Copy,
  Check,
  Shield,
  Globe,
  ChevronRight,
  Terminal,
  Code2,
  Key,
} from 'lucide-react';

interface PublishedEndpoint {
  id: string;
  slug: string;
  name: string;
  description: string;
  datastore_id: string;
  query_pipeline_id: string;
  auth_required: boolean;
  workspace_id: string;
  status: string;
  api_key: string | null;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-surface-700 hover:bg-surface-600 text-text-muted hover:text-text-primary transition-colors"
      title="Copy to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  return (
    <div className="relative group">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-800 border border-border-secondary rounded-t-lg text-xs text-text-muted font-mono">
        {language}
      </div>
      <pre className="bg-surface-900 border border-t-0 border-border-secondary rounded-b-lg p-4 overflow-x-auto text-sm text-text-secondary font-mono leading-relaxed">
        <code>{code}</code>
      </pre>
      <CopyButton text={code} />
    </div>
  );
}

export function PublishPage() {
  const [searchParams] = useSearchParams();
  const preselectedPipeline = searchParams.get('pipeline') || '';

  const [step, setStep] = useState(1);
  const [datastores, setDatastores] = useState<DataStore[]>([]);
  const [pipelines, setPipelines] = useState<QueryPipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState('');
  const [publishedEndpoints, setPublishedEndpoints] = useState<PublishedEndpoint[]>([]);

  // Step 1
  const [selectedDatastoreId, setSelectedDatastoreId] = useState('');
  // Step 2
  const [selectedPipelineId, setSelectedPipelineId] = useState('');
  // Step 3
  const [endpointName, setEndpointName] = useState('');
  const [endpointDescription, setEndpointDescription] = useState('');
  const [authRequired, setAuthRequired] = useState(true);
  // After publish
  const [published, setPublished] = useState<PublishedEndpoint | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [dsRes, qpRes, pubRes] = await Promise.all([
          ingestionApi.listDataStores(),
          queryPipelineApi.list(),
          client.get<{ endpoints: PublishedEndpoint[] }>('/api/v1/ingestion/publish').catch(() => ({ data: { endpoints: [] } })),
        ]);
        setDatastores(dsRes.data.datastores);
        setPipelines(qpRes.data.query_pipelines);
        setPublishedEndpoints(pubRes.data.endpoints);
        // Pre-select pipeline from query params (coming from Chat page)
        if (preselectedPipeline && qpRes.data.query_pipelines.some((p: QueryPipeline) => p.id === preselectedPipeline)) {
          setSelectedPipelineId(preselectedPipeline);
        }
      } catch {
        setError('Failed to load datastores or query pipelines.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selectedDatastore = datastores.find((d) => d.id === selectedDatastoreId);
  const selectedPipeline = pipelines.find((p) => p.id === selectedPipelineId);

  const canProceed = (s: number) => {
    if (s === 1) return !!selectedDatastoreId;
    if (s === 2) return !!selectedPipelineId;
    if (s === 3) return endpointName.trim().length > 0;
    return false;
  };

  const handlePublish = async () => {
    setPublishing(true);
    setError('');
    try {
      const slug = slugify(endpointName);
      const res = await client.post<PublishedEndpoint>('/api/v1/ingestion/publish', {
        name: endpointName,
        slug,
        datastore_id: selectedDatastoreId,
        query_pipeline_id: selectedPipelineId,
        description: endpointDescription,
      });
      setPublished(res.data);
    } catch {
      setError('Failed to publish endpoint. Please try again.');
    } finally {
      setPublishing(false);
    }
  };

  const baseUrl = `${window.location.origin}/api/v1/ingestion/publish`;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-accent-400" />
      </div>
    );
  }

  if (published) {
    const endpointUrl = `${baseUrl}/${published.slug}/query`;

    const curlSnippet = `curl -X POST "${endpointUrl}" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${published.api_key}" \\
  -d '{"query": "What is retrieval augmented generation?", "top_k": 5}'`;

    const pythonSnippet = `import requests

url = "${endpointUrl}"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${published.api_key}",
}
payload = {
    "query": "What is retrieval augmented generation?",
    "top_k": 5,
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()
print(result["answer"])
for source in result["sources"]:
    print(f"  - {source}")`;

    const jsSnippet = `const response = await fetch("${endpointUrl}", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${published.api_key}",
  },
  body: JSON.stringify({
    query: "What is retrieval augmented generation?",
    top_k: 5,
  }),
});

const result = await response.json();
console.log(result.answer);
result.sources.forEach((source) => console.log("  -", source));`;

    return (
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Success header */}
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-6 flex items-start gap-4">
          <CheckCircle2 className="w-6 h-6 text-green-400 mt-0.5 shrink-0" />
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Endpoint Published Successfully</h2>
            <p className="text-sm text-text-secondary mt-1">
              Your endpoint <span className="font-mono text-accent-400">{published.name}</span> is now live and ready to accept queries.
            </p>
          </div>
        </div>

        {/* Endpoint details */}
        <div className="bg-surface-800 border border-border-primary rounded-xl p-6 space-y-4">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Endpoint Details</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-text-muted">Name</span>
              <p className="text-text-primary font-medium">{published.name}</p>
            </div>
            <div>
              <span className="text-text-muted">Status</span>
              <p className="text-green-400 font-medium capitalize">{published.status}</p>
            </div>
            <div>
              <span className="text-text-muted">Slug</span>
              <p className="text-text-primary font-mono">{published.slug}</p>
            </div>
            <div>
              <span className="text-text-muted">Authentication</span>
              <p className="text-text-primary">{published.auth_required ? 'Required' : 'Public'}</p>
            </div>
          </div>

          <div>
            <span className="text-text-muted text-sm">API Endpoint URL</span>
            <div className="relative mt-1">
              <pre className="bg-surface-900 border border-border-secondary rounded-lg p-3 pr-12 text-sm text-accent-400 font-mono overflow-x-auto">
                {endpointUrl}
              </pre>
              <CopyButton text={endpointUrl} />
            </div>
          </div>

          {published.api_key && (
            <div>
              <span className="text-text-muted text-sm flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5" /> API Key
              </span>
              <div className="relative mt-1">
                <pre className="bg-surface-900 border border-border-secondary rounded-lg p-3 pr-12 text-sm text-yellow-400 font-mono overflow-x-auto">
                  {published.api_key}
                </pre>
                <CopyButton text={published.api_key} />
              </div>
              <p className="text-xs text-text-muted mt-1">Save this key securely. It will not be shown again.</p>
            </div>
          )}
        </div>

        {/* Code snippets */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Integration Examples</h3>

          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-2 text-sm text-text-secondary">
                <Terminal className="w-4 h-4" /> cURL
              </div>
              <CodeBlock code={curlSnippet} language="bash" />
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2 text-sm text-text-secondary">
                <Code2 className="w-4 h-4" /> Python
              </div>
              <CodeBlock code={pythonSnippet} language="python" />
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2 text-sm text-text-secondary">
                <Code2 className="w-4 h-4" /> JavaScript
              </div>
              <CodeBlock code={jsSnippet} language="javascript" />
            </div>
          </div>
        </div>

        {/* Publish another */}
        <button
          onClick={() => {
            setPublished(null);
            setStep(1);
            setSelectedDatastoreId('');
            setSelectedPipelineId('');
            setEndpointName('');
            setEndpointDescription('');
            setAuthRequired(true);
          }}
          className="text-sm text-accent-400 hover:text-accent-300 transition-colors"
        >
          Publish another endpoint
        </button>
      </div>
    );
  }

  const steps = [
    { num: 1, label: 'Knowledge Store', icon: Database },
    { num: 2, label: 'Query Pipeline', icon: Search },
    { num: 3, label: 'Configure', icon: Settings2 },
    { num: 4, label: 'Review & Publish', icon: Rocket },
  ];

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
          <Rocket className="w-6 h-6 text-accent-400" />
          Publish Endpoint
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Publish a Knowledge Store + Retrieval Pipeline combo as a queryable API endpoint.
        </p>
      </div>

      {/* Published Endpoints list */}
      {publishedEndpoints.length > 0 && (
        <div className="bg-surface-800 border border-border-primary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Published Endpoints ({publishedEndpoints.length})</h3>
          <div className="space-y-3">
            {publishedEndpoints.map(ep => {
              const isActive = ep.status === 'active';
              return (
                <div key={ep.id} className="flex items-center justify-between px-4 py-3 bg-surface-900 rounded-xl border border-border-secondary">
                  <div className="flex items-center gap-3 min-w-0">
                    <Globe className={`w-4 h-4 shrink-0 ${isActive ? 'text-green-400' : 'text-text-muted'}`} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text-primary truncate">{ep.name}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                          isActive ? 'bg-green-500/10 text-green-400' : 'bg-surface-700 text-text-muted'
                        }`}>{ep.status}</span>
                      </div>
                      <span className="text-xs text-text-muted font-mono">{baseUrl}/{ep.slug}/query</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={async () => {
                        await navigator.clipboard.writeText(`${baseUrl}/${ep.slug}/query`);
                      }}
                      className="p-1.5 rounded-md hover:bg-surface-700 text-text-muted hover:text-text-primary transition-colors"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          await client.patch(`/api/v1/ingestion/publish/${ep.id}`, {
                            status: isActive ? 'disabled' : 'active',
                          });
                          setPublishedEndpoints(prev => prev.map(e =>
                            e.id === ep.id ? { ...e, status: isActive ? 'disabled' : 'active' } : e
                          ));
                        } catch { setError('Failed to update endpoint'); }
                      }}
                      className={`text-xs px-2 py-1 rounded-md transition-colors ${
                        isActive ? 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20' : 'bg-green-500/10 text-green-400 hover:bg-green-500/20'
                      }`}
                    >
                      {isActive ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      onClick={async () => {
                        if (!window.confirm(`Delete endpoint "${ep.name}"?`)) return;
                        try {
                          await client.delete(`/api/v1/ingestion/publish/${ep.id}`);
                          setPublishedEndpoints(prev => prev.filter(e => e.id !== ep.id));
                        } catch { setError('Failed to delete endpoint'); }
                      }}
                      className="p-1.5 rounded-md hover:bg-red-500/10 text-text-muted hover:text-red-400 transition-colors"
                    >
                      <span className="text-xs">Delete</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <div key={s.num} className="flex items-center">
            <button
              onClick={() => s.num < step && setStep(s.num)}
              disabled={s.num > step}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                s.num === step
                  ? 'bg-accent-500/15 text-accent-400 font-medium'
                  : s.num < step
                    ? 'text-text-secondary hover:text-text-primary cursor-pointer'
                    : 'text-text-muted cursor-not-allowed'
              }`}
            >
              <s.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{s.label}</span>
            </button>
            {i < steps.length - 1 && <ChevronRight className="w-4 h-4 text-text-muted mx-1" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">{error}</div>
      )}

      {/* Step 1: Select Knowledge Store */}
      {step === 1 && (
        <div className="bg-surface-800 border border-border-primary rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Select Knowledge Store</h2>
          <p className="text-sm text-text-secondary">Choose the datastore that contains the ingested documents you want to make queryable.</p>

          {datastores.length === 0 ? (
            <p className="text-sm text-text-muted">No datastores found. Create a Knowledge Store first.</p>
          ) : (
            <div className="space-y-2">
              {datastores.map((ds) => (
                <button
                  key={ds.id}
                  onClick={() => setSelectedDatastoreId(ds.id)}
                  className={`w-full text-left p-4 rounded-lg border transition-colors ${
                    selectedDatastoreId === ds.id
                      ? 'border-accent-500 bg-accent-500/10'
                      : 'border-border-secondary bg-surface-900 hover:border-border-primary'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Database className="w-5 h-5 text-accent-400 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text-primary">{ds.name}</p>
                      {ds.description && (
                        <p className="text-xs text-text-muted mt-0.5 truncate">{ds.description}</p>
                      )}
                      <p className="text-xs text-text-muted mt-0.5">
                        Status: <span className="capitalize">{ds.status}</span> | Documents: {ds.source_document_ids.length}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="flex justify-end">
            <button
              onClick={() => setStep(2)}
              disabled={!canProceed(1)}
              className="px-4 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next: Select Pipeline
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Select Query Pipeline */}
      {step === 2 && (
        <div className="bg-surface-800 border border-border-primary rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Select Query Pipeline</h2>
          <p className="text-sm text-text-secondary">Choose the retrieval pipeline that will process incoming queries.</p>

          {pipelines.length === 0 ? (
            <p className="text-sm text-text-muted">No query pipelines found. Create a Query Pipeline first.</p>
          ) : (
            <div className="space-y-2">
              {pipelines.map((qp) => (
                <button
                  key={qp.id}
                  onClick={() => setSelectedPipelineId(qp.id)}
                  className={`w-full text-left p-4 rounded-lg border transition-colors ${
                    selectedPipelineId === qp.id
                      ? 'border-accent-500 bg-accent-500/10'
                      : 'border-border-secondary bg-surface-900 hover:border-border-primary'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Search className="w-5 h-5 text-accent-400 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text-primary">{qp.name}</p>
                      {qp.description && (
                        <p className="text-xs text-text-muted mt-0.5 truncate">{qp.description}</p>
                      )}
                      <p className="text-xs text-text-muted mt-0.5">
                        Strategy: {qp.retrieval_strategy} | Model: {qp.generator.model}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="flex justify-between">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 rounded-lg border border-border-secondary text-text-secondary text-sm hover:bg-surface-700 transition-colors"
            >
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={!canProceed(2)}
              className="px-4 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next: Configure
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Configure */}
      {step === 3 && (
        <div className="bg-surface-800 border border-border-primary rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Configure Endpoint</h2>
          <p className="text-sm text-text-secondary">Set the name, description, and authentication settings for your endpoint.</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Endpoint Name *</label>
              <input
                type="text"
                value={endpointName}
                onChange={(e) => setEndpointName(e.target.value)}
                placeholder="e.g. My Research Assistant"
                className="w-full px-3 py-2 rounded-lg bg-surface-900 border border-border-secondary text-text-primary text-sm placeholder-text-muted focus:outline-none focus:border-accent-500 transition-colors"
              />
              {endpointName && (
                <p className="text-xs text-text-muted mt-1">
                  Slug: <span className="font-mono text-accent-400">{slugify(endpointName)}</span>
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
              <textarea
                value={endpointDescription}
                onChange={(e) => setEndpointDescription(e.target.value)}
                placeholder="Describe what this endpoint does..."
                rows={3}
                className="w-full px-3 py-2 rounded-lg bg-surface-900 border border-border-secondary text-text-primary text-sm placeholder-text-muted focus:outline-none focus:border-accent-500 transition-colors resize-none"
              />
            </div>

            <div className="flex items-center gap-3 p-4 rounded-lg bg-surface-900 border border-border-secondary">
              <Shield className="w-5 h-5 text-yellow-400" />
              <div>
                <p className="text-sm font-medium text-text-primary">API Key Authentication</p>
                <p className="text-xs text-text-muted">
                  A unique API key will be generated. Include it in the Authorization header for all requests.
                </p>
              </div>
              <Key className="w-4 h-4 text-text-muted ml-auto" />
            </div>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setStep(2)}
              className="px-4 py-2 rounded-lg border border-border-secondary text-text-secondary text-sm hover:bg-surface-700 transition-colors"
            >
              Back
            </button>
            <button
              onClick={() => setStep(4)}
              disabled={!canProceed(3)}
              className="px-4 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next: Review
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Review & Publish */}
      {step === 4 && (
        <div className="bg-surface-800 border border-border-primary rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-text-primary">Review & Publish</h2>
          <p className="text-sm text-text-secondary">Review your configuration before publishing.</p>

          <div className="space-y-3">
            <div className="p-4 rounded-lg bg-surface-900 border border-border-secondary">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-text-muted">Knowledge Store</span>
                  <p className="text-text-primary font-medium flex items-center gap-1.5 mt-0.5">
                    <Database className="w-3.5 h-3.5 text-accent-400" />
                    {selectedDatastore?.name}
                  </p>
                </div>
                <div>
                  <span className="text-text-muted">Query Pipeline</span>
                  <p className="text-text-primary font-medium flex items-center gap-1.5 mt-0.5">
                    <Search className="w-3.5 h-3.5 text-accent-400" />
                    {selectedPipeline?.name}
                  </p>
                </div>
                <div>
                  <span className="text-text-muted">Endpoint Name</span>
                  <p className="text-text-primary font-medium mt-0.5">{endpointName}</p>
                </div>
                <div>
                  <span className="text-text-muted">Slug</span>
                  <p className="text-text-primary font-mono mt-0.5">{slugify(endpointName)}</p>
                </div>
                <div>
                  <span className="text-text-muted">Authentication</span>
                  <p className="text-text-primary font-medium mt-0.5 flex items-center gap-1.5">
                    {authRequired ? (
                      <>
                        <Shield className="w-3.5 h-3.5 text-yellow-400" /> Required
                      </>
                    ) : (
                      <>
                        <Globe className="w-3.5 h-3.5 text-green-400" /> Public
                      </>
                    )}
                  </p>
                </div>
                {endpointDescription && (
                  <div className="sm:col-span-2">
                    <span className="text-text-muted">Description</span>
                    <p className="text-text-primary mt-0.5">{endpointDescription}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-surface-900 border border-border-secondary text-xs text-text-muted">
              <p>
                After publishing, the endpoint will be available at:{' '}
                <span className="font-mono text-accent-400">
                  {baseUrl}/{slugify(endpointName)}/query
                </span>
              </p>
            </div>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setStep(3)}
              className="px-4 py-2 rounded-lg border border-border-secondary text-text-secondary text-sm hover:bg-surface-700 transition-colors"
            >
              Back
            </button>
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="px-6 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {publishing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Publishing...
                </>
              ) : (
                <>
                  <Rocket className="w-4 h-4" /> Publish Endpoint
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
