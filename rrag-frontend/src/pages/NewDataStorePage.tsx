import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ingestionApi,
  type IngestionDocument,
  type IngestionPipeline,
  type IngestionPipelineDetail,
  type IngestionComponent,
  type DataStore,
} from '../api/ingestion';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  Database,
  FileText,
  GitBranch,
  PlayCircle,
  Upload,
  Check,
  ChevronRight,
  ChevronLeft,
  Plus,
  Trash2,
  X,
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Eye,
  Zap,
  Network,
  Layers,
  BookOpen,
  Sparkles,
  Search,
  Target,
  Image,
  Brain,
} from 'lucide-react';

// ── Ingestion pipeline templates ──────────────────────────────────
interface PipelineTemplate {
  id: string;
  name: string;
  description: string;
  icon: typeof Zap;
  badge?: string;
  steps: { component: string; config: Record<string, unknown> }[];
}

const PIPELINE_TEMPLATES: PipelineTemplate[] = [
  {
    id: 'quick_ingest',
    name: 'Quick Ingest',
    description: 'Simple & fast: parse multi-format docs, recursive chunk, embed, index to Qdrant. Best for getting started.',
    icon: Zap,
    badge: 'Recommended',
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt', 'csv', 'json'] } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 512, chunk_overlap: 50 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 50 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_quick', dimension: 1536, distance: 'cosine' } },
    ],
  },
  {
    id: 'lightrag',
    name: 'LightRAG',
    description: 'Graph-based: extract entities/relations, embed to Qdrant, build knowledge graph in Neo4j. Best for entity-rich docs.',
    icon: Network,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'lightrag.token_chunker', config: { chunk_token_size: 1200, chunk_overlap_token_size: 100 } },
      { component: 'lightrag.entity_extractor', config: { llm_model: 'gpt-4o-mini', entity_types: ['Person', 'Organization', 'Location', 'Event', 'Concept', 'Technology'], max_gleaning: 1 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 100 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_lightrag', dimension: 1536, distance: 'cosine' } },
      { component: 'lightrag.graph_builder', config: { merge_strategy: 'merge_descriptions', dedup_threshold: 0.9 } },
      { component: 'lightrag.neo4j_graph', config: {} },
    ],
  },
  {
    id: 'kag',
    name: 'KAG (Knowledge Augmented Generation)',
    description: 'Schema-driven knowledge graph: semantic chunking, dual schema-free + schema-constrained extraction, hierarchical subgraph.',
    icon: Layers,
    badge: 'Advanced',
    steps: [
      { component: 'kag.file_reader', config: { content_field: 'content', id_field: 'id' } },
      { component: 'kag.semantic_chunker', config: { max_chunk_size: 500 } },
      { component: 'kag.schema_free_extractor', config: { llm_model: 'gpt-4o-mini' } },
      { component: 'kag.schema_constrained_extractor', config: { llm_model: 'gpt-4o-mini', schema: { entity_types: { Person: ['name', 'role', 'affiliation'], Organization: ['name', 'type', 'location'], Technology: ['name', 'category', 'version'] }, relation_types: ['works_at', 'develops', 'uses', 'part_of', 'located_in'] } } },
      { component: 'kag.subgraph_builder', config: { add_chunk_links: true } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small' } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_kag', dimension: 1536, distance: 'cosine' } },
      { component: 'lightrag.redis_kv', config: { key_prefix: 'rrag:kag:' } },
    ],
  },
  {
    id: 'corag',
    name: 'CoRAG (Chain-of-Retrieval)',
    description: 'Optimized for multi-hop queries: parse, fine-grained chunk, embed, index to Qdrant with Redis cache for iterative retrieval.',
    icon: BookOpen,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'lightrag.token_chunker', config: { chunk_token_size: 512, chunk_overlap_token_size: 50 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 100 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_corag', dimension: 1536, distance: 'cosine' } },
      { component: 'lightrag.redis_kv', config: { key_prefix: 'rrag:corag:' } },
    ],
  },
  {
    id: 'ultrarag',
    name: 'UltraRAG',
    description: 'Modular multi-format ingestion with recursive chunking. Supports PDF, DOCX, EPUB, MD, TXT.',
    icon: Sparkles,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt', 'epub'] } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 512, chunk_overlap: 50 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 100 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_ultrarag', dimension: 1536, distance: 'cosine' } },
      { component: 'lightrag.redis_kv', config: { key_prefix: 'rrag:ultrarag:' } },
    ],
  },
  {
    id: 'opensearch',
    name: 'OpenSearch Full-Text',
    description: 'Index to OpenSearch for hybrid keyword + vector search. Best when you need BM25 full-text capabilities.',
    icon: Search,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt', 'csv', 'json'] } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 512, chunk_overlap: 50 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 50 } },
      { component: 'opensearch_indexer', config: { host: 'opensearch', port: 9200, index_name: 'rrag_default' } },
    ],
  },
  {
    id: 'parent_child_chunking',
    name: 'Parent-Child Chunking',
    description: 'Hierarchical: large parent chunks for context, small child chunks for precise retrieval. Links children to parents at query time.',
    icon: Layers,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 1500, chunk_overlap: 200, output_field: 'parent_chunks' } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 256, chunk_overlap: 30, parent_field: 'parent_chunks', output_field: 'child_chunks' } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 100, input_field: 'child_chunks' } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_parent_child', dimension: 1536, distance: 'cosine', payload_fields: ['parent_id', 'parent_text'] } },
    ],
  },
  {
    id: 'contextual_ingestion',
    name: 'Contextual Ingestion',
    description: 'Anthropic-style: prepends LLM-generated context to each chunk for -49% retrieval failures. Higher cost, much better recall.',
    icon: BookOpen,
    badge: 'High Accuracy',
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 512, chunk_overlap: 50 } },
      { component: 'contextual.context_generator', config: { llm_model: 'claude-sonnet-4-20250514', prompt_template: 'Situate this chunk within the overall document. Give a short context prefix.', max_tokens: 128 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 50, input_field: 'contextualized_text' } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_contextual', dimension: 1536, distance: 'cosine' } },
    ],
  },
  {
    id: 'proposition_based',
    name: 'Proposition-Based',
    description: 'Dense X: decomposes text into atomic propositions for higher recall. Each proposition is independently embedded and indexed.',
    icon: Target,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 1024, chunk_overlap: 100 } },
      { component: 'proposition.decomposer', config: { llm_model: 'gpt-4o-mini', max_propositions_per_chunk: 20 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 200, input_field: 'propositions' } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_propositions', dimension: 1536, distance: 'cosine', payload_fields: ['source_chunk_id', 'proposition_text'] } },
    ],
  },
  {
    id: 'multi_modal',
    name: 'Multi-Modal',
    description: 'Text, table, and image parsing with specialized chunkers and unified index. Handles PDFs with figures, charts, and complex layouts.',
    icon: Image,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'pptx', 'html'], extract_images: true, extract_tables: true } },
      { component: 'multimodal.table_parser', config: { output_format: 'markdown', include_headers: true } },
      { component: 'multimodal.image_captioner', config: { model: 'gpt-4o-mini', max_tokens: 256 } },
      { component: 'ultrarag.recursive_chunker', config: { chunk_size: 512, chunk_overlap: 50 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 50 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_multimodal', dimension: 1536, distance: 'cosine', payload_fields: ['content_type', 'source_page'] } },
    ],
  },
  {
    id: 'semantic_chunking',
    name: 'Semantic Chunking',
    description: 'Meaning-aware splitting that respects topic boundaries. Uses embedding similarity to detect natural breakpoints in text.',
    icon: Brain,
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'semantic.embedding_chunker', config: { model: 'text-embedding-3-small', similarity_threshold: 0.75, min_chunk_size: 100, max_chunk_size: 1500 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 100 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_semantic', dimension: 1536, distance: 'cosine' } },
    ],
  },
  {
    id: 'graphrag_full',
    name: 'GraphRAG Full',
    description: 'Complete LightRAG + KAG hybrid with both vector and graph indexing. Community summaries, entity extraction, and hierarchical graph.',
    icon: Network,
    badge: 'Advanced',
    steps: [
      { component: 'ultrarag.multi_parser', config: { formats: ['pdf', 'docx', 'md', 'txt'] } },
      { component: 'lightrag.token_chunker', config: { chunk_token_size: 1200, chunk_overlap_token_size: 100 } },
      { component: 'lightrag.entity_extractor', config: { llm_model: 'gpt-4o-mini', entity_types: ['Person', 'Organization', 'Location', 'Event', 'Concept', 'Technology'], max_gleaning: 2 } },
      { component: 'kag.schema_constrained_extractor', config: { llm_model: 'gpt-4o-mini', schema: { entity_types: { Person: ['name', 'role'], Organization: ['name', 'type'], Technology: ['name', 'category'] }, relation_types: ['works_at', 'develops', 'uses', 'part_of'] } } },
      { component: 'graphrag.community_summarizer', config: { llm_model: 'gpt-4o-mini', max_community_size: 50 } },
      { component: 'openai_embedder', config: { model: 'text-embedding-3-small', batch_size: 100 } },
      { component: 'qdrant_indexer', config: { url: 'http://qdrant:6333', collection_name: 'rrag_graphrag_full', dimension: 1536, distance: 'cosine' } },
      { component: 'lightrag.graph_builder', config: { merge_strategy: 'merge_descriptions', dedup_threshold: 0.85 } },
      { component: 'lightrag.neo4j_graph', config: {} },
      { component: 'lightrag.redis_kv', config: { key_prefix: 'rrag:graphrag:' } },
    ],
  },
];

const STEPS = [
  { label: 'Knowledge Store', icon: Database, description: 'Name your knowledge store' },
  { label: 'Documents', icon: FileText, description: 'Upload or select files' },
  { label: 'Pipeline', icon: GitBranch, description: 'Choose ingestion pipeline' },
  { label: 'Run', icon: PlayCircle, description: 'Review and start' },
] as const;

const ALLOWED_EXTENSIONS = new Set([
  '.pdf', '.txt', '.md', '.csv', '.json', '.jsonl',
  '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.html', '.htm', '.xml', '.yaml', '.yml',
]);

const MAX_FILE_SIZE = 100 * 1024 * 1024;

function validateFiles(files: File[]): string | null {
  for (const file of files) {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext)) return `Unsupported file type: ${ext} (${file.name})`;
    if (file.size > MAX_FILE_SIZE) return `File too large: ${file.name} (${Math.round(file.size / 1024 / 1024)} MB, max 100 MB)`;
  }
  return null;
}

export function NewDataStorePage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState('');

  // Step 1: DataStore
  const [dsName, setDsName] = useState('');
  const [dsDescription, setDsDescription] = useState('');
  const [createdDs, setCreatedDs] = useState<DataStore | null>(null);

  // Step 2: Documents
  const [documents, setDocuments] = useState<IngestionDocument[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Step 3: Pipeline
  type PipelineMode = 'template' | 'existing' | 'custom';
  const [pipelineMode, setPipelineMode] = useState<PipelineMode>('template');
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [pipelines, setPipelines] = useState<IngestionPipeline[]>([]);
  const [components, setComponents] = useState<IngestionComponent[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState('');
  const [pipelineDetail, setPipelineDetail] = useState<IngestionPipelineDetail | null>(null);
  const [newPipeName, setNewPipeName] = useState('');
  const [newPipeDesc, setNewPipeDesc] = useState('');
  const [newPipeSteps, setNewPipeSteps] = useState<{ component: string; config: Record<string, unknown> }[]>([]);
  const [creatingFromTemplate, setCreatingFromTemplate] = useState(false);

  // Step 4: Running
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  // Load documents
  const loadDocuments = useCallback(async () => {
    try {
      const { data } = await ingestionApi.listDocuments();
      setDocuments(Array.isArray(data?.documents) ? data.documents : []);
    } catch {
      setError('Failed to load documents');
    }
  }, []);

  // Load pipelines + components
  const loadPipelines = useCallback(async () => {
    try {
      const [pipeRes, compRes] = await Promise.all([
        ingestionApi.listPipelines(),
        ingestionApi.listComponents(),
      ]);
      setPipelines(Array.isArray(pipeRes.data?.pipelines) ? pipeRes.data.pipelines : []);
      setComponents(Array.isArray(compRes.data?.components) ? compRes.data.components : []);
    } catch {
      setError('Failed to load pipelines');
    }
  }, []);

  // Load data when entering relevant steps
  useEffect(() => {
    if (currentStep === 1) loadDocuments();
    if (currentStep === 2) loadPipelines();
  }, [currentStep, loadDocuments, loadPipelines]);

  // Load pipeline detail when selected
  useEffect(() => {
    if (!selectedPipeline) { setPipelineDetail(null); return; }
    (async () => {
      try {
        const { data } = await ingestionApi.getPipeline(selectedPipeline);
        setPipelineDetail(data);
      } catch {
        setPipelineDetail(null);
      }
    })();
  }, [selectedPipeline]);

  // Step 1 handlers
  const handleCreateDataStore = async () => {
    if (!dsName.trim()) return;
    setError('');
    try {
      const { data } = await ingestionApi.createDataStore({ name: dsName.trim(), description: dsDescription.trim() || undefined });
      setCreatedDs(data);
      setCurrentStep(1);
    } catch {
      setError('Failed to create datastore. The name may already be taken.');
    }
  };

  // Step 2 handlers
  const handleUpload = async () => {
    const files = fileRef.current?.files;
    if (!files?.length) return;
    const fileList = Array.from(files);
    const validationError = validateFiles(fileList);
    if (validationError) { setError(validationError); return; }
    setUploading(true);
    setError('');
    try {
      const { data } = await ingestionApi.uploadDocuments(fileList);
      fileRef.current!.value = '';
      await loadDocuments();
      // Auto-select the newly uploaded docs
      if (data?.uploaded) {
        const newIds = data.uploaded.map((u: { id: string }) => u.id);
        setSelectedDocIds((prev) => [...new Set([...prev, ...newIds])]);
      }
    } catch {
      setError('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev) => prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]);
  };

  const toggleAllDocs = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(documents.map((d) => d.id));
    }
  };

  // Step 3 handlers
  const handleSelectTemplate = (templateId: string) => {
    setSelectedTemplate(templateId);
    setPipelineMode('template');
    setSelectedPipeline(''); // clear any existing selection
  };

  const handleCreatePipelineFromTemplate = async () => {
    const tpl = PIPELINE_TEMPLATES.find((t) => t.id === selectedTemplate);
    if (!tpl || !createdDs) return;
    setCreatingFromTemplate(true);
    setError('');
    const pipeName = `${createdDs.name}-${tpl.id}`;
    try {
      await ingestionApi.createPipeline({ name: pipeName, description: tpl.description, steps: tpl.steps });
      setSelectedPipeline(pipeName);
      await loadPipelines();
      return pipeName;
    } catch {
      setError('Failed to create pipeline from template');
      return null;
    } finally {
      setCreatingFromTemplate(false);
    }
  };

  const handleCreatePipeline = async () => {
    if (!newPipeName || newPipeSteps.length === 0 || newPipeSteps.some((s) => !s.component)) return;
    setError('');
    try {
      await ingestionApi.createPipeline({ name: newPipeName, description: newPipeDesc || undefined, steps: newPipeSteps });
      setNewPipeName('');
      setNewPipeDesc('');
      setNewPipeSteps([]);
      setPipelineMode('existing');
      await loadPipelines();
      setSelectedPipeline(newPipeName);
    } catch {
      setError('Failed to create pipeline');
    }
  };

  // Step 4 handler
  const handleRunIngestion = async () => {
    if (!createdDs || selectedDocIds.length === 0) return;
    setSubmitting(true);
    setError('');
    try {
      // If using a template, create the pipeline first
      let pipelineName = selectedPipeline;
      if (pipelineMode === 'template' && !selectedPipeline && selectedTemplate) {
        const created = await handleCreatePipelineFromTemplate();
        if (!created) { setSubmitting(false); return; }
        pipelineName = created;
      }
      if (!pipelineName) { setSubmitting(false); return; }
      const { data } = await ingestionApi.createJob({
        pipeline_name: pipelineName,
        document_ids: selectedDocIds,
        datastore_id: createdDs.id,
      });
      setJobId(data.job_id);
    } catch {
      setError('Failed to start ingestion job');
      setSubmitting(false);
    }
  };

  const getSelectedTemplateName = () => {
    if (pipelineMode === 'template' && selectedTemplate) {
      return PIPELINE_TEMPLATES.find((t) => t.id === selectedTemplate)?.name || '';
    }
    return selectedPipeline;
  };

  const canProceed = (step: number) => {
    switch (step) {
      case 0: return !!createdDs;
      case 1: return selectedDocIds.length > 0;
      case 2: return pipelineMode === 'template' ? !!selectedTemplate : !!selectedPipeline;
      case 3: return false; // final step
      default: return false;
    }
  };

  const goNext = () => {
    if (currentStep < STEPS.length - 1 && canProceed(currentStep)) {
      setError('');
      setCurrentStep(currentStep + 1);
    }
  };

  const goBack = () => {
    if (currentStep > 0) {
      setError('');
      setCurrentStep(currentStep - 1);
    }
  };

  // --- Success screen ---
  if (jobId) {
    return (
      <div className="animate-fade-in max-w-2xl mx-auto py-12">
        <div className="bg-surface-800 rounded-2xl border border-border-primary p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <CheckCircle2 className="w-8 h-8 text-emerald-400" />
          </div>
          <h2 className="text-xl font-bold text-text-primary mb-2">Ingestion Started!</h2>
          <p className="text-text-secondary mb-1">
            DataStore <span className="font-medium text-text-primary">{createdDs?.name}</span> is being populated.
          </p>
          <p className="text-text-muted text-sm mb-6">
            Pipeline <span className="font-mono">{getSelectedTemplateName()}</span> is processing {selectedDocIds.length} document(s).
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => navigate(`/ingestion/jobs/${jobId}`)}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 transition-all"
            >
              <Eye className="w-4 h-4" />
              Track Job Progress
            </button>
            <button
              onClick={() => navigate('/ingestion/datastores')}
              className="flex items-center gap-1.5 px-5 py-2.5 border border-border-primary text-text-secondary text-sm rounded-lg hover:bg-surface-700 transition-colors"
            >
              <Database className="w-4 h-4" />
              View DataStores
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate('/ingestion/datastores')}
          className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-700 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-text-primary">New DataStore</h1>
          <p className="text-sm text-text-muted">Create a datastore and start ingesting documents</p>
        </div>
      </div>

      {/* Stepper */}
      <div className="mb-8">
        <div className="flex items-center">
          {STEPS.map((step, i) => {
            const StepIcon = step.icon;
            const isCompleted = i < currentStep;
            const isCurrent = i === currentStep;
            return (
              <div key={step.label} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <div className="flex items-center w-full">
                    {i > 0 && (
                      <div className={`flex-1 h-0.5 transition-colors duration-300 ${isCompleted ? 'bg-accent-500' : 'bg-border-primary'}`} />
                    )}
                    <button
                      onClick={() => { if (isCompleted) { setError(''); setCurrentStep(i); } }}
                      disabled={!isCompleted && !isCurrent}
                      className={`relative w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
                        isCompleted
                          ? 'bg-accent-500 text-white cursor-pointer hover:bg-accent-400'
                          : isCurrent
                          ? 'bg-accent-500/20 text-accent-400 ring-2 ring-accent-500/50'
                          : 'bg-surface-800 text-text-muted border border-border-primary'
                      }`}
                    >
                      {isCompleted ? <Check className="w-4 h-4" /> : <StepIcon className="w-4 h-4" />}
                    </button>
                    {i < STEPS.length - 1 && (
                      <div className={`flex-1 h-0.5 transition-colors duration-300 ${isCompleted ? 'bg-accent-500' : 'bg-border-primary'}`} />
                    )}
                  </div>
                  <div className="mt-2 text-center">
                    <div className={`text-xs font-medium ${isCurrent ? 'text-accent-400' : isCompleted ? 'text-text-primary' : 'text-text-muted'}`}>
                      {step.label}
                    </div>
                    <div className="text-[10px] text-text-muted hidden sm:block">{step.description}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError('')} className="text-red-500 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Step Content */}
      <div className="bg-surface-800 rounded-2xl border border-border-primary overflow-hidden">
        {/* ===== Step 1: DataStore ===== */}
        {currentStep === 0 && (
          <div className="p-6 animate-fade-in">
            <h2 className="text-lg font-semibold text-text-primary mb-1">Create DataStore</h2>
            <p className="text-sm text-text-muted mb-5">A datastore holds your indexed documents for RAG queries.</p>
            <div className="space-y-4 max-w-lg">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Name <span className="text-red-400">*</span></label>
                <input
                  type="text"
                  value={dsName}
                  onChange={(e) => setDsName(e.target.value)}
                  placeholder="e.g. legal-docs-v1"
                  disabled={!!createdDs}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-500 disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Description</label>
                <textarea
                  value={dsDescription}
                  onChange={(e) => setDsDescription(e.target.value)}
                  placeholder="What will this datastore contain?"
                  rows={2}
                  disabled={!!createdDs}
                  className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-500 disabled:opacity-50 resize-none"
                />
              </div>
              {!createdDs ? (
                <button
                  onClick={handleCreateDataStore}
                  disabled={!dsName.trim()}
                  className="flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                >
                  <Database className="w-4 h-4" />
                  Create DataStore
                </button>
              ) : (
                <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm text-emerald-400">DataStore <strong>{createdDs.name}</strong> created successfully</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===== Step 2: Documents ===== */}
        {currentStep === 1 && (
          <div className="p-6 animate-fade-in">
            <h2 className="text-lg font-semibold text-text-primary mb-1">Select Documents</h2>
            <p className="text-sm text-text-muted mb-5">Upload new files or select existing documents to ingest into your datastore.</p>

            {/* Upload area */}
            <div className="mb-5 p-4 border-2 border-dashed border-border-primary rounded-xl bg-surface-900/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-accent-500/10 flex items-center justify-center shrink-0">
                  <Upload className="w-5 h-5 text-accent-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <input
                    ref={fileRef}
                    type="file"
                    multiple
                    accept={Array.from(ALLOWED_EXTENSIONS).join(',')}
                    className="text-sm text-text-secondary file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-surface-700 file:text-text-primary hover:file:bg-surface-600 file:cursor-pointer file:transition-colors"
                  />
                </div>
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-50 transition-all shrink-0"
                >
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
              <p className="text-xs text-text-muted mt-2">
                Supported: PDF, TXT, MD, CSV, JSON, DOCX, XLSX, PPTX, HTML, XML, YAML (max 100 MB each)
              </p>
            </div>

            {/* Document list */}
            {documents.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="w-10 h-10 mx-auto text-text-muted mb-2 opacity-40" />
                <p className="text-text-muted text-sm">No documents available. Upload some files above.</p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">
                    {selectedDocIds.length} of {documents.length} selected
                  </span>
                  <button onClick={toggleAllDocs} className="text-xs text-accent-400 hover:text-accent-300 transition-colors">
                    {selectedDocIds.length === documents.length ? 'Deselect All' : 'Select All'}
                  </button>
                </div>
                <div className="border border-border-primary rounded-xl overflow-hidden max-h-64 overflow-y-auto">
                  {documents.map((doc) => (
                    <label
                      key={doc.id}
                      className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer border-b border-border-primary last:border-0 transition-colors ${
                        selectedDocIds.includes(doc.id) ? 'bg-accent-500/5' : 'hover:bg-surface-700/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocIds.includes(doc.id)}
                        onChange={() => toggleDoc(doc.id)}
                        className="accent-accent-500 w-4 h-4"
                      />
                      <FileText className="w-4 h-4 text-text-muted shrink-0" />
                      <span className="text-sm text-text-primary flex-1 truncate">{doc.filename}</span>
                      <span className="text-xs text-text-muted shrink-0">{doc.content_type}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* ===== Step 3: Pipeline ===== */}
        {currentStep === 2 && (
          <div className="p-6 animate-fade-in">
            <h2 className="text-lg font-semibold text-text-primary mb-1">Select Ingestion Pipeline</h2>
            <p className="text-sm text-text-muted mb-5">Pick a template, use an existing pipeline, or build a custom one.</p>

            {/* Mode tabs */}
            <div className="flex gap-1 p-1 bg-surface-900 rounded-lg mb-5">
              {([
                { key: 'template' as const, label: 'Templates', count: PIPELINE_TEMPLATES.length },
                { key: 'existing' as const, label: 'Existing', count: pipelines.length },
                { key: 'custom' as const, label: 'Custom', count: null },
              ]).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setPipelineMode(tab.key)}
                  className={`flex-1 px-3 py-2 text-sm font-medium rounded-md transition-all ${
                    pipelineMode === tab.key
                      ? 'bg-surface-700 text-text-primary shadow-sm'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {tab.label}
                  {tab.count !== null && <span className="ml-1.5 text-xs opacity-60">({tab.count})</span>}
                </button>
              ))}
            </div>

            {/* ── Template cards ── */}
            {pipelineMode === 'template' && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {PIPELINE_TEMPLATES.map((tpl) => {
                    const TplIcon = tpl.icon;
                    const isSelected = selectedTemplate === tpl.id;
                    return (
                      <button
                        key={tpl.id}
                        onClick={() => handleSelectTemplate(tpl.id)}
                        className={`relative text-left p-4 rounded-xl border transition-all ${
                          isSelected
                            ? 'border-accent-500/50 bg-accent-500/5 ring-1 ring-accent-500/30'
                            : 'border-border-primary bg-surface-900 hover:bg-surface-700/50 hover:border-border-primary/80'
                        }`}
                      >
                        {tpl.badge && (
                          <span className="absolute top-3 right-3 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            {tpl.badge}
                          </span>
                        )}
                        <div className="flex items-start gap-3">
                          <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                            isSelected ? 'bg-accent-500/20 text-accent-400' : 'bg-surface-800 text-text-muted'
                          }`}>
                            <TplIcon className="w-5 h-5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm text-text-primary">{tpl.name}</span>
                              {isSelected && <CheckCircle2 className="w-4 h-4 text-accent-400 shrink-0" />}
                            </div>
                            <p className="text-xs text-text-muted mt-1 leading-relaxed">{tpl.description}</p>
                          </div>
                        </div>
                        {/* Step preview */}
                        <div className="flex items-center gap-1 mt-3 ml-12 flex-wrap">
                          {tpl.steps.map((step, si) => (
                            <div key={si} className="flex items-center gap-1">
                              {si > 0 && <ChevronRight className="w-2.5 h-2.5 text-text-muted" />}
                              <span className="text-[11px] px-1.5 py-0.5 bg-surface-800 border border-border-primary rounded text-text-secondary">
                                {step.component.replace(/_/g, ' ')}
                              </span>
                            </div>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Existing pipelines ── */}
            {pipelineMode === 'existing' && (
              <div>
                {pipelines.length > 0 ? (
                  <div className="space-y-2">
                    {pipelines.map((p) => (
                      <button
                        key={p.name}
                        onClick={() => { setSelectedPipeline(p.name); setSelectedTemplate(null); }}
                        className={`w-full text-left p-4 rounded-xl border transition-all ${
                          selectedPipeline === p.name
                            ? 'border-accent-500/50 bg-accent-500/5 ring-1 ring-accent-500/30'
                            : 'border-border-primary bg-surface-900 hover:bg-surface-700/50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <GitBranch className="w-4 h-4 text-accent-400" />
                              <span className="font-medium text-sm text-text-primary">{p.name}</span>
                            </div>
                            <div className="text-xs text-text-muted mt-0.5 ml-6">{p.steps} steps{p.description ? ` \u2014 ${p.description}` : ''}</div>
                          </div>
                          {selectedPipeline === p.name && (
                            <CheckCircle2 className="w-5 h-5 text-accent-400 shrink-0" />
                          )}
                        </div>
                      </button>
                    ))}
                    {/* Pipeline preview */}
                    {pipelineDetail && (
                      <div className="mt-3 p-4 bg-surface-900 rounded-xl border border-border-primary">
                        <h3 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-3">Pipeline Steps</h3>
                        <div className="flex items-center gap-2 flex-wrap">
                          {pipelineDetail.steps.map((step, i) => (
                            <div key={i} className="flex items-center gap-2">
                              {i > 0 && <ChevronRight className="w-3 h-3 text-text-muted" />}
                              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-800 border border-border-primary rounded-lg">
                                <span className="w-5 h-5 flex items-center justify-center bg-accent-500/10 text-accent-400 rounded-full text-[10px] font-bold shrink-0">
                                  {i + 1}
                                </span>
                                <span className="text-xs text-text-primary">{step.component}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <GitBranch className="w-10 h-10 mx-auto text-text-muted mb-2 opacity-40" />
                    <p className="text-text-muted text-sm">No existing pipelines. Try a template or create a custom one.</p>
                  </div>
                )}
              </div>
            )}

            {/* ── Custom pipeline builder ── */}
            {pipelineMode === 'custom' && (
              <div className="border border-accent-500/30 bg-accent-500/5 rounded-xl p-5 animate-scale-in">
                <h3 className="font-semibold text-text-primary mb-4">Build Custom Pipeline</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Name <span className="text-red-400">*</span></label>
                    <input
                      value={newPipeName}
                      onChange={(e) => setNewPipeName(e.target.value)}
                      placeholder="e.g. pdf-to-vectors"
                      className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-1">Description</label>
                    <input
                      value={newPipeDesc}
                      onChange={(e) => setNewPipeDesc(e.target.value)}
                      placeholder="Optional description"
                      className="w-full bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-sm font-medium text-text-secondary">Steps <span className="text-red-400">*</span></label>
                      <button
                        onClick={() => setNewPipeSteps([...newPipeSteps, { component: '', config: {} }])}
                        className="text-accent-400 text-xs hover:text-accent-300 flex items-center gap-1"
                      >
                        <Plus className="w-3 h-3" /> Add Step
                      </button>
                    </div>
                    {newPipeSteps.length === 0 && (
                      <p className="text-xs text-text-muted py-2">Add at least one step to define the pipeline.</p>
                    )}
                    {newPipeSteps.map((step, i) => (
                      <div key={i} className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-text-muted w-5 text-center shrink-0">{i + 1}.</span>
                        <select
                          value={step.component}
                          onChange={(e) => {
                            const updated = [...newPipeSteps];
                            updated[i] = { ...updated[i], component: e.target.value };
                            setNewPipeSteps(updated);
                          }}
                          className="flex-1 bg-surface-900 border border-border-primary rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-500"
                        >
                          <option value="">Select component...</option>
                          {components.map((c) => (
                            <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                          ))}
                        </select>
                        <button
                          onClick={() => setNewPipeSteps(newPipeSteps.filter((_, idx) => idx !== i))}
                          className="text-red-400 hover:text-red-300 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={handleCreatePipeline}
                    disabled={!newPipeName || newPipeSteps.length === 0 || newPipeSteps.some((s) => !s.component)}
                    className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 transition-all"
                  >
                    <GitBranch className="w-4 h-4" />
                    Create Pipeline
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ===== Step 4: Review & Run ===== */}
        {currentStep === 3 && (() => {
          const activeTpl = pipelineMode === 'template' && selectedTemplate
            ? PIPELINE_TEMPLATES.find((t) => t.id === selectedTemplate)
            : null;
          const TplIcon = activeTpl?.icon || GitBranch;
          return (
          <div className="p-6 animate-fade-in">
            <h2 className="text-lg font-semibold text-text-primary mb-1">Review & Start Ingestion</h2>
            <p className="text-sm text-text-muted mb-5">Verify everything looks correct, then start the ingestion job.</p>

            <div className="space-y-4">
              {/* DataStore summary */}
              <div className="p-4 bg-surface-900 rounded-xl border border-border-primary">
                <div className="flex items-center gap-2 mb-2">
                  <Database className="w-4 h-4 text-accent-400" />
                  <h3 className="text-sm font-medium text-text-primary">DataStore</h3>
                </div>
                <div className="ml-6 space-y-1">
                  <div className="text-sm text-text-secondary">
                    <span className="text-text-muted">Name:</span> <span className="font-medium text-text-primary">{createdDs?.name}</span>
                  </div>
                  {createdDs?.description && (
                    <div className="text-sm text-text-secondary">
                      <span className="text-text-muted">Description:</span> {createdDs.description}
                    </div>
                  )}
                  <div className="text-sm">
                    <StatusBadge status="draft" />
                  </div>
                </div>
              </div>

              {/* Documents summary */}
              <div className="p-4 bg-surface-900 rounded-xl border border-border-primary">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-accent-400" />
                  <h3 className="text-sm font-medium text-text-primary">Documents ({selectedDocIds.length})</h3>
                </div>
                <div className="ml-6 space-y-0.5 max-h-32 overflow-y-auto">
                  {documents
                    .filter((d) => selectedDocIds.includes(d.id))
                    .map((doc) => (
                      <div key={doc.id} className="flex items-center gap-2 text-sm text-text-secondary">
                        <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                        <span className="truncate">{doc.filename}</span>
                        <span className="text-xs text-text-muted shrink-0">{doc.content_type}</span>
                      </div>
                    ))}
                </div>
              </div>

              {/* Pipeline summary */}
              <div className="p-4 bg-surface-900 rounded-xl border border-border-primary">
                <div className="flex items-center gap-2 mb-2">
                  <TplIcon className="w-4 h-4 text-accent-400" />
                  <h3 className="text-sm font-medium text-text-primary">Pipeline</h3>
                  {activeTpl?.badge && (
                    <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {activeTpl.badge}
                    </span>
                  )}
                </div>
                <div className="ml-6">
                  <div className="text-sm text-text-secondary mb-2">
                    <span className="text-text-muted">
                      {activeTpl ? 'Template:' : 'Name:'}
                    </span>{' '}
                    <span className="font-medium text-text-primary">{getSelectedTemplateName()}</span>
                    {activeTpl && <span className="text-text-muted"> ({activeTpl.steps.length} steps)</span>}
                    {pipelineDetail && !activeTpl && <span className="text-text-muted"> ({pipelineDetail.steps.length} steps)</span>}
                  </div>
                  {activeTpl && (
                    <>
                      <p className="text-xs text-text-muted mb-2">{activeTpl.description}</p>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {activeTpl.steps.map((step, i) => (
                          <div key={i} className="flex items-center gap-1">
                            {i > 0 && <ChevronRight className="w-3 h-3 text-text-muted" />}
                            <span className="text-xs px-2 py-0.5 bg-surface-800 border border-border-primary rounded text-text-secondary">
                              {step.component.replace(/_/g, ' ')}
                            </span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                  {pipelineDetail && !activeTpl && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {pipelineDetail.steps.map((step, i) => (
                        <div key={i} className="flex items-center gap-1">
                          {i > 0 && <ChevronRight className="w-3 h-3 text-text-muted" />}
                          <span className="text-xs px-2 py-0.5 bg-surface-800 border border-border-primary rounded text-text-secondary">
                            {step.component}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Run button */}
              <button
                onClick={handleRunIngestion}
                disabled={submitting || creatingFromTemplate}
                className="w-full flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-xl hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 transition-all shadow-lg shadow-emerald-500/20"
              >
                {submitting || creatingFromTemplate ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {creatingFromTemplate ? 'Creating Pipeline...' : 'Starting Ingestion...'}
                  </>
                ) : (
                  <>
                    <PlayCircle className="w-5 h-5" />
                    Start Ingestion
                  </>
                )}
              </button>
            </div>
          </div>
          );
        })()}

        {/* Navigation footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border-primary bg-surface-900/50">
          <button
            onClick={goBack}
            disabled={currentStep === 0}
            className="flex items-center gap-1.5 px-4 py-2 text-sm text-text-secondary hover:text-text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </button>
          <div className="text-xs text-text-muted">
            Step {currentStep + 1} of {STEPS.length}
          </div>
          {currentStep < STEPS.length - 1 && (
            <button
              onClick={goNext}
              disabled={!canProceed(currentStep)}
              className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-accent-500 to-accent-600 text-white text-sm font-medium rounded-lg hover:from-accent-400 hover:to-accent-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
          {currentStep === STEPS.length - 1 && <div />}
        </div>
      </div>
    </div>
  );
}
