import { useState, useRef, useEffect, useCallback, type FormEvent } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  chatApi,
  queryPipelineApi,
  streamChat,
  type ChatSource,
  type ChatTrace,
  type QueryPipeline,
  type SSEEvent,
} from '../api/chat';
import {
  Send,
  Bot,
  User,
  Loader2,
  FileText,
  Trash2,
  Plus,
  ChevronDown,
  ChevronUp,
  Zap,
  Clock,
  X,
  Settings2,
  Search,
  Activity,
  AlertTriangle,
  File,
  Rocket,
} from 'lucide-react';

interface CompareResult {
  pipeline: string;
  pipelineId: string;
  answer: string;
  sources: ChatSource[];
  traces: ChatTrace[];
  durationMs: number;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  traces?: ChatTrace[];
  model?: string;
  tokensUsed?: number;
  durationMs?: number;
  timestamp: Date;
  compareResults?: CompareResult[];
}

interface ConversationMeta {
  id: string;
  title: string;
  lastMessage: string;
  createdAt: Date;
}

export function ChatPage() {
  const [searchParams] = useSearchParams();
  const qpIds = searchParams.getAll('qp');

  const [mode, setMode] = useState<'single' | 'compare'>('single');
  const [pipelines, setPipelines] = useState<QueryPipeline[]>([]);
  const [selectedPipelineIds, setSelectedPipelineIds] = useState<string[]>(qpIds);
  const [compareStreaming, setCompareStreaming] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [_streamingSources, setStreamingSources] = useState<ChatSource[]>([]);
  const [streamingTraces, setStreamingTraces] = useState<ChatTrace[]>([]);
  const [error, setError] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [model, setModel] = useState('gpt-4o-mini');
  const [temperature, setTemperature] = useState(0.7);
  const [expandedSources, setExpandedSources] = useState<string | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [conversationId]);

  // Load available query pipelines
  useEffect(() => {
    queryPipelineApi.list().then(({ data }) => {
      setPipelines(data.query_pipelines);
      // If URL had qp params, use those; otherwise select all
      if (qpIds.length === 0 && data.query_pipelines.length > 0) {
        setSelectedPipelineIds(data.query_pipelines.map((p) => p.id));
      }
    }).catch(() => setPipelines([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault();
    const msg = input.trim();
    if (!msg || loading || selectedPipelineIds.length === 0) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: msg,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setError('');
    setStreamingContent('');
    setStreamingSources([]);
    setStreamingTraces([]);
    setCompareStreaming({});

    if (mode === 'compare' && selectedPipelineIds.length > 1) {
      // Compare mode: stream from each pipeline independently
      const cancellers: (() => void)[] = [];
      const results: Record<string, CompareResult> = {};
      let completedCount = 0;
      const totalPipelines = selectedPipelineIds.length;

      for (const pipelineId of selectedPipelineIds) {
        const pipelineMeta = pipelines.find((p) => p.id === pipelineId);
        const pipelineName = pipelineMeta?.name ?? pipelineId;
        const startTime = Date.now();

        const cancel = streamChat(
          {
            message: msg,
            query_pipeline_ids: [pipelineId],
            model,
            temperature,
            conversation_id: null,
          },
          (evt: SSEEvent) => {
            switch (evt.type) {
              case 'token':
                setCompareStreaming((prev) => ({
                  ...prev,
                  [pipelineId]: (prev[pipelineId] ?? '') + evt.content,
                }));
                break;
              case 'done': {
                const elapsed = Date.now() - startTime;
                results[pipelineId] = {
                  pipeline: pipelineName,
                  pipelineId,
                  answer: evt.answer,
                  sources: evt.sources,
                  traces: evt.traces,
                  durationMs: elapsed,
                };
                completedCount++;
                if (completedCount >= totalPipelines) {
                  const compareResults = selectedPipelineIds.map((id) => results[id]).filter(Boolean);
                  const assistantMsg: ChatMessage = {
                    id: crypto.randomUUID(),
                    role: 'assistant',
                    content: '',
                    compareResults,
                    model,
                    timestamp: new Date(),
                  };
                  setMessages((prev) => [...prev, assistantMsg]);
                  setCompareStreaming({});
                  setLoading(false);

                  setConversations((prev) => {
                    const title = msg.slice(0, 50) + (msg.length > 50 ? '...' : '');
                    const id = crypto.randomUUID();
                    return [
                      { id, title, lastMessage: `Compared ${totalPipelines} pipelines`, createdAt: new Date() },
                      ...prev,
                    ];
                  });
                }
                break;
              }
              case 'error':
                completedCount++;
                results[pipelineId] = {
                  pipeline: pipelineName,
                  pipelineId,
                  answer: `Error: ${evt.message}`,
                  sources: [],
                  traces: [],
                  durationMs: Date.now() - startTime,
                };
                if (completedCount >= totalPipelines) {
                  const compareResults = selectedPipelineIds.map((id) => results[id]).filter(Boolean);
                  const assistantMsg: ChatMessage = {
                    id: crypto.randomUUID(),
                    role: 'assistant',
                    content: '',
                    compareResults,
                    model,
                    timestamp: new Date(),
                  };
                  setMessages((prev) => [...prev, assistantMsg]);
                  setCompareStreaming({});
                  setLoading(false);
                }
                break;
            }
          },
          (err) => {
            completedCount++;
            results[pipelineId] = {
              pipeline: pipelineName,
              pipelineId,
              answer: `Error: ${err.message}`,
              sources: [],
              traces: [],
              durationMs: Date.now() - startTime,
            };
            if (completedCount >= totalPipelines) {
              const compareResults = selectedPipelineIds.map((id) => results[id]).filter(Boolean);
              const assistantMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: '',
                compareResults,
                model,
                timestamp: new Date(),
              };
              setMessages((prev) => [...prev, assistantMsg]);
              setCompareStreaming({});
              setLoading(false);
            }
          },
        );
        cancellers.push(cancel);
      }

      abortRef.current = () => cancellers.forEach((c) => c());
    } else {
      // Single mode: existing behavior
      let finalConvId = conversationId;

      const cancel = streamChat(
        {
          message: msg,
          query_pipeline_ids: selectedPipelineIds,
          model,
          temperature,
          conversation_id: conversationId,
        },
        (evt: SSEEvent) => {
          switch (evt.type) {
            case 'start':
              if (!finalConvId) {
                finalConvId = evt.conversation_id;
                setConversationId(evt.conversation_id);
              }
              break;
            case 'sources':
              setStreamingSources((prev) => [...prev, ...evt.sources]);
              break;
            case 'trace':
              setStreamingTraces((prev) => [...prev, evt.trace]);
              break;
            case 'token':
              setStreamingContent((prev) => prev + evt.content);
              break;
            case 'done': {
              const assistantMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: evt.answer,
                sources: evt.sources,
                traces: evt.traces,
                model,
                timestamp: new Date(),
              };
              setMessages((prev) => [...prev, assistantMsg]);
              setStreamingContent('');
              setStreamingSources([]);
              setStreamingTraces([]);
              setLoading(false);

              if (finalConvId) {
                setConversations((prev) => {
                  if (prev.find((c) => c.id === finalConvId)) return prev;
                  return [
                    {
                      id: finalConvId!,
                      title: msg.slice(0, 50) + (msg.length > 50 ? '...' : ''),
                      lastMessage: evt.answer.slice(0, 80),
                      createdAt: new Date(),
                    },
                    ...prev,
                  ];
                });
              }
              break;
            }
            case 'error':
              setError(evt.message);
              setLoading(false);
              break;
          }
        },
        (err) => {
          setError(err.message);
          setLoading(false);
        },
      );

      abortRef.current = cancel;
    }
  }, [input, loading, selectedPipelineIds, model, temperature, conversationId, mode, pipelines]);

  const startNewConversation = () => {
    if (abortRef.current) abortRef.current();
    setMessages([]);
    setConversationId(null);
    setError('');
    setStreamingContent('');
  };

  const handleDeleteConversation = async (id: string) => {
    try {
      await chatApi.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (conversationId === id) startNewConversation();
    } catch { /* ignore */ }
  };

  const togglePipeline = (id: string) => {
    if (mode === 'single') {
      setSelectedPipelineIds([id]);
    } else {
      setSelectedPipelineIds((prev) =>
        prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
      );
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  };

  const noPipelines = pipelines.length === 0;
  const noneSelected = selectedPipelineIds.length === 0;

  return (
    <div className="flex h-[calc(100vh-3.5rem-3rem)] -m-6 animate-fade-in">
      {/* Conversation sidebar */}
      <div className="w-64 bg-surface-900 border-r border-border-primary flex flex-col">
        <div className="p-3 border-b border-border-primary">
          <button
            onClick={startNewConversation}
            className="w-full flex items-center justify-center gap-1.5 py-2 px-3 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border-primary">
          <button
            onClick={() => {
              setMode('single');
              setSelectedPipelineIds((prev) => prev.length > 0 ? [prev[0]] : []);
            }}
            className={`px-3 py-1 text-xs font-medium rounded-lg transition-all ${
              mode === 'single'
                ? 'bg-accent-500/20 text-accent-400 ring-1 ring-accent-500/30'
                : 'text-text-muted hover:text-text-secondary hover:bg-surface-800'
            }`}
          >
            Single
          </button>
          <button
            onClick={() => setMode('compare')}
            className={`px-3 py-1 text-xs font-medium rounded-lg transition-all ${
              mode === 'compare'
                ? 'bg-accent-500/20 text-accent-400 ring-1 ring-accent-500/30'
                : 'text-text-muted hover:text-text-secondary hover:bg-surface-800'
            }`}
          >
            Compare
          </button>
        </div>

        {/* Query Pipeline selector */}
        <div className="p-3 border-b border-border-primary">
          <div className="text-[10px] font-semibold text-text-muted uppercase tracking-widest mb-2">
            Query Pipelines
          </div>
          {noPipelines ? (
            <Link
              to="/query-pipelines"
              className="flex items-center gap-1.5 px-2 py-1.5 text-xs text-accent-400 hover:text-accent-300"
            >
              <Plus className="w-3 h-3" />
              Create a query pipeline first
            </Link>
          ) : (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {pipelines.map((p) => (
                <label
                  key={p.id}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg text-xs cursor-pointer hover:bg-surface-800 transition-colors"
                >
                  <input
                    type={mode === 'single' ? 'radio' : 'checkbox'}
                    name={mode === 'single' ? 'pipeline-select' : undefined}
                    checked={selectedPipelineIds.includes(p.id)}
                    onChange={() => togglePipeline(p.id)}
                    className="rounded accent-accent-500 w-3 h-3"
                  />
                  <Search className="w-3 h-3 text-text-muted shrink-0" />
                  <span className="text-text-secondary truncate">{p.name}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Publish shortcut */}
        {selectedPipelineIds.length > 0 && mode === 'single' && (
          <div className="px-3 pb-2">
            <Link
              to={`/publish?pipeline=${selectedPipelineIds[0]}`}
              className="flex items-center justify-center gap-1.5 w-full px-3 py-1.5 rounded-lg bg-surface-700 hover:bg-surface-600 text-text-secondary hover:text-text-primary text-xs transition-colors border border-border-secondary"
            >
              <Rocket className="w-3 h-3" />
              Publish as API
            </Link>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <p className="text-xs text-text-muted text-center py-6">No conversations yet</p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-start gap-2 p-2.5 rounded-lg cursor-pointer transition-all ${
                  conversationId === conv.id
                    ? 'bg-accent-500/10 border border-accent-500/30'
                    : 'hover:bg-surface-800 border border-transparent'
                }`}
                onClick={() => setConversationId(conv.id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text-primary truncate">{conv.title}</div>
                  <div className="text-xs text-text-muted truncate mt-0.5">{conv.lastMessage}</div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                  className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-red-400 transition-all p-0.5"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="h-12 bg-surface-900 border-b border-border-primary flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-accent-400" />
            <span className="text-sm font-medium text-text-primary">RAG Chat</span>
            {selectedPipelineIds.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent-500/10 text-accent-400 ring-1 ring-accent-500/20">
                <Search className="w-3 h-3" />
                {selectedPipelineIds.length} pipeline(s)
              </span>
            )}
            {conversationId && (
              <span className="text-xs text-text-muted font-mono">{conversationId.slice(0, 8)}</span>
            )}
          </div>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1.5 rounded-lg transition-colors ${
              showSettings ? 'bg-accent-500/10 text-accent-400' : 'text-text-muted hover:text-text-primary hover:bg-surface-800'
            }`}
          >
            <Settings2 className="w-4 h-4" />
          </button>
        </div>

        {/* Settings */}
        {showSettings && (
          <div className="bg-surface-900 border-b border-border-primary px-4 py-3 flex items-center gap-6 animate-slide-up">
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="bg-surface-800 border border-border-primary rounded-lg px-2 py-1 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
              >
                <option value="gpt-4o-mini">GPT-4o Mini</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted">Temperature</label>
              <input
                type="range" min="0" max="2" step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-24 accent-accent-500"
              />
              <span className="text-xs text-text-secondary w-6">{temperature}</span>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {noPipelines ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center animate-fade-in">
                <AlertTriangle className="w-12 h-12 text-yellow-400 mx-auto mb-4" />
                <h2 className="text-lg font-semibold text-text-primary mb-2">No Query Pipelines</h2>
                <p className="text-sm text-text-muted max-w-md mb-4">
                  You need to create a query pipeline before you can chat. Query pipelines define how your datastores are queried.
                </p>
                <Link
                  to="/query-pipelines"
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent-500 text-white text-sm rounded-lg hover:bg-accent-400 transition-all"
                >
                  <Plus className="w-4 h-4" />
                  Create Query Pipeline
                </Link>
              </div>
            </div>
          ) : messages.length === 0 && !streamingContent ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center animate-fade-in">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-accent-500/20 to-highlight-500/20 flex items-center justify-center">
                  <Zap className="w-8 h-8 text-accent-400" />
                </div>
                <h2 className="text-lg font-semibold text-text-primary mb-2">RAG Chat</h2>
                <p className="text-sm text-text-muted max-w-md">
                  {noneSelected
                    ? 'Select at least one query pipeline from the sidebar to start chatting.'
                    : 'Ask questions and the LLM will use your query pipelines as tools to find relevant information.'}
                </p>
                {!noneSelected && (
                  <div className="flex flex-wrap gap-2 justify-center mt-6">
                    {['What documents are in this dataset?', 'Summarize the key findings', 'What are the main topics?'].map((s) => (
                      <button
                        key={s}
                        onClick={() => setInput(s)}
                        className="px-3 py-1.5 bg-surface-800 border border-border-primary rounded-lg text-xs text-text-secondary hover:bg-surface-700 hover:text-text-primary transition-all"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className={`mx-auto py-4 space-y-4 px-4 ${mode === 'compare' ? 'max-w-5xl' : 'max-w-3xl'}`}>
              {messages.map((msg) =>
                msg.compareResults && msg.compareResults.length > 0 ? (
                  <div key={msg.id} className="animate-slide-up">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-500 to-highlight-600 flex items-center justify-center shrink-0">
                        <Bot className="w-3.5 h-3.5 text-white" />
                      </div>
                      <span className="text-xs text-text-muted">
                        Compared {msg.compareResults.length} pipeline{msg.compareResults.length > 1 ? 's' : ''}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {msg.compareResults.map((result) => (
                        <div key={result.pipelineId} className="border border-border-primary rounded-xl p-4 bg-surface-800">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-semibold text-accent-400">{result.pipeline}</h4>
                            <span className="flex items-center gap-0.5 text-[10px] text-text-muted">
                              <Clock className="w-2.5 h-2.5" />
                              {(result.durationMs / 1000).toFixed(1)}s
                            </span>
                          </div>
                          <p className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
                            {result.answer}
                          </p>
                          {result.sources.length > 0 && (
                            <div className="mt-3 pt-2 border-t border-border-primary">
                              <div className="text-[10px] text-text-muted mb-1">
                                {result.sources.length} source(s)
                              </div>
                              <div className="space-y-1">
                                {result.sources.slice(0, 3).map((src, i) => {
                                  const filename = (src.metadata?.filename || '') as string;
                                  return (
                                    <div key={src.id || i} className="text-[10px] text-text-muted truncate flex items-center gap-1">
                                      <span className="font-bold text-accent-400">[{i + 1}]</span>
                                      {filename ? (
                                        <span className="flex items-center gap-1">
                                          <File className="w-2.5 h-2.5 text-accent-400 shrink-0" />
                                          {filename}
                                        </span>
                                      ) : (
                                        <span className="italic">Unknown source</span>
                                      )}
                                      <span className="ml-auto shrink-0">{Math.round(src.score * 100)}%</span>
                                    </div>
                                  );
                                })}
                                {result.sources.length > 3 && (
                                  <div className="text-[10px] text-text-muted">
                                    +{result.sources.length - 3} more
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                          {result.traces.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-border-primary">
                              {result.traces.map((trace) => (
                                <div key={trace.id} className="text-[10px] text-text-muted flex items-center gap-1">
                                  <Activity className="w-2.5 h-2.5 text-highlight-400" />
                                  {trace.pipeline_name}: {trace.total_duration_ms.toFixed(0)}ms
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <MessageBubble
                    key={msg.id}
                    msg={msg}
                    expandedSources={expandedSources}
                    setExpandedSources={setExpandedSources}
                    expandedTraces={expandedTraces}
                    setExpandedTraces={setExpandedTraces}
                  />
                ),
              )}

              {/* Streaming indicator */}
              {loading && mode === 'compare' && Object.keys(compareStreaming).length > 0 ? (
                <div className="animate-fade-in">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-500 to-highlight-600 flex items-center justify-center shrink-0">
                      <Bot className="w-3.5 h-3.5 text-white" />
                    </div>
                    <div className="flex items-center gap-2 text-xs text-text-muted">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Comparing pipelines...
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {selectedPipelineIds.map((pId) => {
                      const pMeta = pipelines.find((p) => p.id === pId);
                      return (
                        <div key={pId} className="border border-border-primary rounded-xl p-4 bg-surface-800">
                          <h4 className="text-xs font-semibold text-accent-400 mb-2">
                            {pMeta?.name ?? pId}
                          </h4>
                          {compareStreaming[pId] ? (
                            <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
                              {compareStreaming[pId]}
                              <span className="inline-block w-1.5 h-4 bg-accent-400 animate-pulse ml-0.5 align-text-bottom" />
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 text-sm text-text-muted">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Thinking...
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : loading && (
                <div className="flex gap-3 animate-fade-in">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-500 to-highlight-600 flex items-center justify-center shrink-0">
                    <Bot className="w-3.5 h-3.5 text-white" />
                  </div>
                  <div className="bg-surface-800 border border-border-primary rounded-xl px-4 py-3 max-w-[80%]">
                    {streamingContent ? (
                      <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
                        {streamingContent}
                        <span className="inline-block w-1.5 h-4 bg-accent-400 animate-pulse ml-0.5 align-text-bottom" />
                      </div>
                    ) : streamingTraces.length > 0 ? (
                      <div className="space-y-1">
                        {streamingTraces.map((t, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-xs text-text-muted">
                            <Activity className="w-3 h-3 text-accent-400" />
                            Searched "{t.query}" via {t.pipeline_name} ({t.total_duration_ms.toFixed(0)}ms)
                          </div>
                        ))}
                        <div className="flex items-center gap-1.5 text-xs text-text-muted">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Generating response...
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-sm text-text-muted">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Thinking...
                      </div>
                    )}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mx-4 mb-2 p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-red-500 hover:text-red-300 ml-2">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-border-primary bg-surface-900 p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                noneSelected
                  ? 'Select a query pipeline to start chatting...'
                  : 'Ask a question...'
              }
              disabled={noneSelected}
              rows={1}
              className="flex-1 resize-none bg-surface-800 border border-border-primary rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent disabled:opacity-50 transition-all"
              style={{ maxHeight: '120px' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = Math.min(target.scrollHeight, 120) + 'px';
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || loading || noneSelected}
              className="flex items-center justify-center w-10 h-10 bg-gradient-to-r from-accent-500 to-accent-600 text-white rounded-xl hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shrink-0"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}


// ── Message bubble component ──────────────────────────────────────────

function MessageBubble({
  msg,
  expandedSources,
  setExpandedSources,
  expandedTraces,
  setExpandedTraces,
}: {
  msg: ChatMessage;
  expandedSources: string | null;
  setExpandedSources: (v: string | null) => void;
  expandedTraces: string | null;
  setExpandedTraces: (v: string | null) => void;
}) {
  return (
    <div className={`flex gap-3 animate-slide-up ${msg.role === 'user' ? 'justify-end' : ''}`}>
      {msg.role === 'assistant' && (
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-500 to-highlight-600 flex items-center justify-center shrink-0 mt-0.5">
          <Bot className="w-3.5 h-3.5 text-white" />
        </div>
      )}
      <div
        className={`max-w-[80%] ${
          msg.role === 'user'
            ? 'bg-accent-500/10 border border-accent-500/20'
            : 'bg-surface-800 border border-border-primary'
        } rounded-xl px-4 py-3`}
      >
        <div className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
          {msg.content}
        </div>

        {/* Source citations */}
        {msg.sources && msg.sources.length > 0 && (() => {
          const maxScore = Math.max(...msg.sources.map(s => s.score), 0.001);
          return (
            <div className="mt-3 pt-3 border-t border-border-primary">
              <button
                onClick={() => setExpandedSources(expandedSources === msg.id ? null : msg.id)}
                className="flex items-center gap-1.5 text-xs text-accent-400 hover:text-accent-300 transition-colors"
              >
                <FileText className="w-3 h-3" />
                {msg.sources.length} source(s)
                {expandedSources === msg.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
              {expandedSources === msg.id && (
                <div className="mt-2 space-y-2">
                  {msg.sources.map((src, i) => {
                    const filename = (src.metadata?.filename || '') as string;
                    const sourceType = (src.metadata?.source || '') as string;
                    const relevancePct = Math.round((src.score / maxScore) * 100);
                    return (
                      <div key={src.id || i} className="p-2.5 bg-surface-900 rounded-lg border border-border-primary">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-[10px] font-bold text-accent-400 shrink-0">[{i + 1}]</span>
                          {filename ? (
                            <span className="text-xs font-medium text-text-primary truncate flex items-center gap-1">
                              <File className="w-3 h-3 text-accent-400 shrink-0" />
                              {filename}
                            </span>
                          ) : (
                            <span className="text-xs text-text-muted italic">Unknown source</span>
                          )}
                          {sourceType && (
                            <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded bg-surface-700 text-text-muted shrink-0">
                              {sourceType}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mb-1.5">
                          <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-accent-500 to-accent-400"
                              style={{ width: `${relevancePct}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-text-muted shrink-0 w-8 text-right">{relevancePct}%</span>
                        </div>
                        <p className="text-xs text-text-muted line-clamp-3 leading-relaxed">{src.content}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })()}

        {/* Trace panel */}
        {msg.traces && msg.traces.length > 0 && (
          <div className="mt-2 pt-2 border-t border-border-primary">
            <button
              onClick={() => setExpandedTraces(expandedTraces === msg.id ? null : msg.id)}
              className="flex items-center gap-1.5 text-xs text-highlight-400 hover:text-highlight-300 transition-colors"
            >
              <Activity className="w-3 h-3" />
              Trace ({msg.traces.length} pipeline call{msg.traces.length > 1 ? 's' : ''})
              {expandedTraces === msg.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {expandedTraces === msg.id && (
              <div className="mt-2 space-y-2">
                {msg.traces.map((trace) => (
                  <div key={trace.id} className="p-2 bg-surface-900 rounded-lg border border-border-primary">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs font-medium text-text-primary">{trace.pipeline_name}</span>
                      {trace.datastore_name && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-500/10 text-accent-400 ring-1 ring-accent-500/20">
                          {trace.datastore_name}
                        </span>
                      )}
                      <span className="text-[10px] text-text-muted">
                        {trace.total_duration_ms.toFixed(0)}ms
                      </span>
                    </div>
                    <div className="text-[10px] text-text-muted mb-1">
                      Query: "{trace.query}"
                    </div>
                    <div className="space-y-0.5">
                      {trace.steps.map((step, i) => (
                        <div key={i} className="flex items-center gap-2 text-[10px]">
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              step.status === 'completed' ? 'bg-green-400' : step.status === 'failed' ? 'bg-red-400' : 'bg-yellow-400'
                            }`}
                          />
                          <span className="text-text-secondary font-mono">{step.step}</span>
                          <span className="text-text-muted">{step.duration_ms.toFixed(0)}ms</span>
                          {step.error && (
                            <span className="text-red-400 truncate">{step.error}</span>
                          )}
                          {step.output_summary && Object.keys(step.output_summary).length > 0 && (
                            <span className="text-text-muted">
                              {Object.entries(step.output_summary).map(([k, v]) => `${k}=${v}`).join(', ')}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Metadata */}
        {msg.role === 'assistant' && (
          <div className="mt-2 flex items-center gap-3 text-[10px] text-text-muted">
            {msg.model && <span>{msg.model}</span>}
            {msg.tokensUsed ? <span>{msg.tokensUsed} tokens</span> : null}
            {msg.durationMs ? (
              <span className="flex items-center gap-0.5">
                <Clock className="w-2.5 h-2.5" />
                {(msg.durationMs / 1000).toFixed(1)}s
              </span>
            ) : null}
          </div>
        )}
      </div>
      {msg.role === 'user' && (
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-3.5 h-3.5 text-white" />
        </div>
      )}
    </div>
  );
}
