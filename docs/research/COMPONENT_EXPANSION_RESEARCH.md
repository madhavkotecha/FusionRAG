# RAG Component Registry Expansion Research (2025-2026)

> Deep research on components **beyond** retrieval and ingestion. Goal: expand from 58 components / 12 categories to 100+ components / 20+ categories.

---

## Current Registry Baseline (58 components, 12 categories)

| Category | Count | Components |
|----------|-------|------------|
| parser | 3 | file_loader, multi_parser, web_scraper |
| chunker | 8 | recursive, semantic, token, sentence, proposition, contextual, hierarchical, document_structure |
| embedder | 9 | openai, sentence_transformer, e5, bge_m3, cohere, jina, nomic, voyage, multimodal |
| extractor | 4 | schema_free, schema_constrained, entity (LightRAG), subquery_decomposer (CoRAG) |
| retriever | 7 | dense, hybrid, graph, web, streaming, table, gfm |
| reranker | 5 | cross_encoder, cohere, jina, llm_listwise, context_compressor |
| generator | 3 | llm_generator, speculative, vision |
| indexer | 2 | faiss, milvus |
| storage | 3 | kv_store, graph_store, vector_store |
| graph_builder | 2 | lightrag, kag_subgraph |
| planner | 3 | corag, mcts, kag |
| agent | 9 | query_router, reflection, memory, tool_use, orchestrator, self_cognition_gate, deep_rag, adaptive_retrieval_controller, rag_evaluator |

---

## New Categories & Components (51 new components, 10 new categories)

---

## 1. Evaluation & Benchmarking (`evaluation`)

### 1.1 `ragas_evaluator` — RAGAS Evaluation Runner

- **Purpose**: Run RAGAS (Retrieval-Augmented Generation Assessment) evaluation suite on pipeline outputs
- **Key Metrics**: faithfulness, answer_relevancy, context_precision, context_recall, context_entity_recall, answer_similarity, answer_correctness
- **Library**: `ragas` (PyPI), open-source, reference-free evaluation using LLM-as-judge
- **Architecture**: Takes (question, answer, contexts, ground_truth) tuples; uses LLM to score each dimension independently
- **Paper**: Shahul Es et al., "RAGAS: Automated Evaluation of Retrieval Augmented Generation" (2023, updated 2025)
- **Input Ports**: `questions` (string_list), `answers` (string_list), `contexts` (list), `ground_truths` (string_list)
- **Output Ports**: `scores` (object), `per_sample_scores` (list)
- **Config**: `metrics` (list of metric names), `llm_provider` (openai/anthropic/litellm), `batch_size`, `raise_exceptions`

### 1.2 `deepeval_evaluator` — DeepEval Test Runner

- **Purpose**: Run DeepEval evaluation with pytest-compatible test-driven development patterns
- **Key Metrics**: hallucination, faithfulness, answer_relevancy, contextual_relevancy, coherence, bias, toxicity, GEval (custom criteria)
- **Library**: `deepeval` (PyPI), supports CI/CD integration, pytest plugin
- **Architecture**: Each metric is a standalone class; wrap in `EvaluationDataset` for batch runs; supports custom `GEval` criteria with natural language rubrics
- **Differentiator from RAGAS**: TDD approach, native pytest integration, broader metric coverage (bias, toxicity), built-in CI/CD quality gates
- **Input Ports**: `test_cases` (list), `metrics` (list)
- **Output Ports**: `results` (object), `passed` (boolean), `report` (object)
- **Config**: `metrics` (list), `threshold` (float per metric), `model` (judge LLM), `async_mode`

### 1.3 `ares_evaluator` — ARES Automated Evaluation

- **Purpose**: Research-grade automated RAG evaluation with synthetic data generation and fine-tuned LLM judges
- **Key Capability**: Trains domain-specific classifier judges; produces statistically confident scores with confidence intervals
- **Paper**: Saad-Falcon et al., "ARES: An Automated Evaluation Framework for RAG Systems" (2024)
- **Architecture**: (1) Generate synthetic QA from corpus, (2) fine-tune judge classifiers on synthetic + gold labels, (3) apply prediction-powered inference (PPI) for confidence intervals
- **Differentiator**: Statistical rigor with confidence bounds; trainable judges vs. prompt-based scoring
- **Input Ports**: `corpus` (document_list), `predictions` (list), `gold_labels` (list, optional)
- **Output Ports**: `scores` (object), `confidence_intervals` (object), `trained_judges` (object)
- **Config**: `judge_model`, `num_synthetic_samples`, `ppi_enabled`, `evaluation_dimensions`

### 1.4 `benchmark_generator` — Synthetic Golden Dataset Creator

- **Purpose**: Auto-generate golden evaluation datasets from a document corpus
- **Libraries**: RAGAS `TestsetGenerator`, Giskard `generate_testset`, custom synthetic pipelines
- **Architecture**: (1) Build internal knowledge graph from source docs, (2) generate questions of controlled complexity (simple, reasoning, multi-context, conditional), (3) produce ground-truth answers with source attribution
- **Paper**: "Know Your RAG: Dataset Taxonomy and Generation Strategies" (arXiv:2411.19710, 2024)
- **Key Feature**: Control distribution of question types; multi-hop and adversarial question generation
- **Input Ports**: `documents` (document_list), `config` (object)
- **Output Ports**: `test_set` (list), `metadata` (object)
- **Config**: `num_samples`, `question_types` (simple/reasoning/multi_context/conditional), `distribution`, `difficulty_levels`, `llm_provider`

### 1.5 `metric_calculator` — Retrieval Metric Calculator

- **Purpose**: Compute standard IR metrics without LLM calls (fast, deterministic)
- **Metrics**: Precision@K, Recall@K, MRR, NDCG, MAP, Hit Rate, F1
- **Architecture**: Pure computation on (query, retrieved_docs, relevant_docs) tuples; no LLM dependency
- **Libraries**: `ranx`, `trec_eval`, custom implementations
- **Input Ports**: `queries` (string_list), `retrieved` (list), `relevant` (list)
- **Output Ports**: `metrics` (object), `per_query_metrics` (list)
- **Config**: `k_values` ([1, 3, 5, 10, 20]), `metrics` (list), `relevance_threshold`

### 1.6 `ab_test_splitter` — A/B Test Traffic Splitter

- **Purpose**: Route queries to different pipeline variants for controlled experimentation
- **Architecture**: Stateless percentage-based routing with consistent hashing (same user always sees same variant); logs variant assignment for downstream analysis
- **Pattern**: Canary/shadow deployment for RAG pipelines
- **Input Ports**: `query` (string), `user_id` (string)
- **Output Ports**: `variant_a_query` (string), `variant_b_query` (string), `assignment` (object)
- **Config**: `split_ratio` (float, default 0.5), `variants` (list of pipeline_ids), `hash_seed`, `sticky_sessions`

### 1.7 `human_annotation_collector` — Human Feedback Interface

- **Purpose**: Collect human judgments on RAG output quality for gold dataset curation
- **Architecture**: Generates annotation tasks with (question, answer, context) triples; supports Likert scales, binary relevance, free-text corrections; exports to evaluation datasets
- **Integration**: Label Studio, Argilla, Prodigy, custom webhook
- **Input Ports**: `samples` (list), `annotation_schema` (object)
- **Output Ports**: `annotations` (list), `inter_annotator_agreement` (float)
- **Config**: `annotation_type` (binary/likert/freetext), `num_annotators`, `export_format`, `webhook_url`

---

## 2. Agentic Orchestration (`orchestrator`)

### 2.1 `intent_classifier` — Query Intent Classifier

- **Purpose**: Classify user intent to route to appropriate pipeline (factual lookup, summarization, comparison, creative, code, etc.)
- **Architecture**: (1) Zero-shot LLM classification, (2) fine-tuned classifier (BERT/DeBERTa), or (3) embedding similarity to intent exemplars
- **Libraries**: `transformers`, `setfit`, `sentence-transformers`
- **Key Intents**: factual_qa, summarization, comparison, how_to, opinion, clarification, out_of_scope
- **Input Ports**: `query` (string)
- **Output Ports**: `intent` (string), `confidence` (float), `all_intents` (object)
- **Config**: `method` (llm/classifier/embedding), `model_name`, `intent_definitions`, `confidence_threshold`

### 2.2 `strategy_selector` — Retrieval Strategy Selector

- **Purpose**: Dynamically select which retrieval strategy to use based on query characteristics
- **Architecture**: Analyzes query complexity, domain, entity density, temporal sensitivity; selects from: dense, sparse, hybrid, graph, web, table, multi-hop
- **Paper**: Adaptive Retrieval Controller concept from "Adaptive-RAG" (Jeong et al., 2024)
- **Input Ports**: `query` (string), `query_analysis` (object)
- **Output Ports**: `strategy` (string), `retriever_config` (object), `reasoning` (string)
- **Config**: `available_strategies` (list), `complexity_thresholds`, `llm_provider`

### 2.3 `self_correction_agent` — Self-Correction Loop Agent

- **Purpose**: Detect insufficient or incorrect answers and trigger re-retrieval or query reformulation
- **Architecture**: Generate answer -> self-critique (check grounding, completeness, relevance) -> if insufficient, reformulate query and re-retrieve -> iterate up to N times
- **Paper**: "Self-RAG: Learning to Retrieve, Generate, and Critique" (Asai et al., 2024); "CRAG: Corrective RAG" (Yan et al., 2024)
- **Key Tokens**: [Retrieve], [IsRel], [IsSup], [IsUse] (from Self-RAG)
- **Input Ports**: `query` (string), `contexts` (list), `initial_answer` (string)
- **Output Ports**: `corrected_answer` (string), `iterations` (integer), `correction_trace` (list)
- **Config**: `max_iterations` (int, default 3), `critique_model`, `correction_strategy` (reformulate/expand/decompose), `quality_threshold`

### 2.4 `multi_agent_coordinator` — Multi-Agent Supervisor

- **Purpose**: Coordinate multiple specialized agents (retriever, reasoner, validator, formatter) through a supervisor pattern
- **Architecture**: Supervisor agent receives task, delegates to specialists, aggregates results, resolves conflicts; supports sequential, parallel, and debate coordination modes
- **Frameworks**: LangGraph (graph-based), CrewAI (role-based), AutoGen (conversation-based)
- **Pattern**: Supervisor -> [Retriever Agent, Reasoner Agent, Fact-Checker Agent, Formatter Agent] -> Supervisor aggregation
- **Input Ports**: `query` (string), `agent_configs` (list)
- **Output Ports**: `response` (string), `agent_outputs` (list), `coordination_trace` (object)
- **Config**: `coordination_mode` (sequential/parallel/debate), `max_rounds`, `conflict_resolution` (vote/supervisor/consensus), `agent_definitions`

### 2.5 `query_decomposer` — Query Decomposition Planner

- **Purpose**: Break complex multi-hop queries into sequential sub-questions
- **Architecture**: LLM-based decomposition with dependency graph; each sub-question answered independently; answers fused at the end
- **Papers**: "DecompRC" (Min et al.), "IRCoT" (Trivedi et al., 2023), Multi-hop RAG patterns
- **Key Feature**: Produces a DAG of sub-queries where later questions can depend on earlier answers
- **Input Ports**: `query` (string)
- **Output Ports**: `sub_queries` (list), `dependency_graph` (object), `decomposition_reasoning` (string)
- **Config**: `max_sub_queries` (int, default 5), `decomposition_model`, `include_dependencies` (bool)

### 2.6 `tool_orchestrator` — Tool-Use Coordinator

- **Purpose**: Select and invoke external tools (calculators, APIs, databases, code interpreters) based on query needs
- **Architecture**: Tool registry with descriptions; LLM selects tool + generates arguments; execute tool; incorporate result into context
- **Frameworks**: OpenAI function calling, Anthropic tool use, LangChain tools, MCP (Model Context Protocol)
- **Input Ports**: `query` (string), `available_tools` (list)
- **Output Ports**: `result` (string), `tool_calls` (list), `tool_outputs` (list)
- **Config**: `tool_definitions` (list), `max_tool_calls` (int), `allow_parallel_tools` (bool), `mcp_servers` (list)

---

## 3. Post-Processing & Quality (`guardrail`)

### 3.1 `hallucination_detector` — Hallucination Detection

- **Purpose**: Detect unsupported claims in generated answers by comparing against retrieved context
- **Architecture**: NLI-based classification (entailment/contradiction/neutral) at sentence level; aggregate to response-level score
- **Papers**: "FACTUM: Mechanistic Detection of Citation Hallucination" (arXiv:2601.05866, Jan 2026); "MetaRAG: Metamorphic Testing for Hallucination Detection" (arXiv:2509.09360); "HalluGraph" (arXiv:2512.01659)
- **Libraries**: `vectara-hallucination-eval` (HHEM), fine-tuned NLI models (DeBERTa-v3-large-mnli), Patronus Lynx
- **Methods**: (1) NLI entailment scoring, (2) atomic factoid decomposition + verification, (3) graph-based grounding (HalluGraph)
- **Input Ports**: `answer` (string), `contexts` (list), `query` (string)
- **Output Ports**: `hallucination_score` (float), `flagged_sentences` (list), `grounding_details` (object)
- **Config**: `method` (nli/factoid/graph), `model_name`, `threshold` (float), `granularity` (sentence/claim)

### 3.2 `citation_generator` — Inline Citation Generator

- **Purpose**: Add source citations to every claim in the generated answer
- **Architecture**: (1) Decompose answer into atomic claims, (2) match each claim to source passage via NLI/embedding similarity, (3) insert inline citations [1][2] with source metadata
- **Paper**: "ReClaim: Refer & Claim" (90% citation accuracy); "Ground Every Sentence" (arXiv:2407.01796)
- **Key Feature**: Sentence-level attribution with bounding box coordinates for PDF sources
- **Input Ports**: `answer` (string), `contexts` (list), `source_metadata` (list)
- **Output Ports**: `cited_answer` (string), `citations` (list), `uncited_claims` (list)
- **Config**: `citation_style` (inline/footnote/endnote), `min_confidence` (float), `include_page_numbers` (bool)

### 3.3 `citation_verifier` — Citation Correctness Verifier

- **Purpose**: Verify that existing citations actually support their associated claims (anti-hallucination for citations)
- **Architecture**: For each (claim, cited_source) pair, run NLI to check entailment; flag post-rationalized citations (up to 57% of citations are post-rationalized per recent research)
- **Paper**: "Correctness is not Faithfulness" (arXiv:2412.18004); GaRAGe benchmark (arXiv:2506.07671)
- **Input Ports**: `cited_answer` (string), `citations` (list), `source_documents` (list)
- **Output Ports**: `verification_results` (list), `accuracy_score` (float), `flagged_citations` (list)
- **Config**: `nli_model`, `threshold`, `flag_post_rationalized` (bool)

### 3.4 `answer_validator` — Answer Quality Validator

- **Purpose**: Validate answer completeness, relevance, and format before returning to user
- **Architecture**: Multi-check pipeline: (1) relevance to query, (2) grounding in context, (3) format compliance, (4) completeness; acts as output gate
- **Integration**: NeMo Guardrails `self_check_output` rail pattern
- **Input Ports**: `query` (string), `answer` (string), `contexts` (list)
- **Output Ports**: `is_valid` (boolean), `validation_scores` (object), `rejection_reason` (string, optional)
- **Config**: `checks` (list: relevance/grounding/format/completeness), `thresholds` (object), `fallback_action` (reject/retry/escalate)

### 3.5 `pii_filter` — PII Detection & Anonymization

- **Purpose**: Detect and mask/redact personally identifiable information in inputs and outputs
- **Library**: Microsoft Presidio (open-source), Private AI, or AWS Comprehend
- **Architecture**: Analyzer (NER + regex + checksums) detects entities; Anonymizer applies operators (redact, replace, mask, hash, encrypt); Deanonymizer can reverse for authorized use
- **Entities**: names, emails, phone numbers, SSNs, credit cards, addresses, dates of birth, IP addresses, bitcoin wallets
- **Integration**: NeMo Guardrails PII flow; Guardrails AI `detect_pii` validator
- **Input Ports**: `text` (string)
- **Output Ports**: `anonymized_text` (string), `detected_entities` (list), `entity_map` (object)
- **Config**: `entities` (list), `action` (redact/mask/hash/encrypt), `language`, `score_threshold` (float), `allow_deanonymize` (bool)

### 3.6 `safety_filter` — Content Safety & Toxicity Filter

- **Purpose**: Block toxic, harmful, biased, or off-topic content in inputs and outputs
- **Libraries**: NeMo Guardrails, Guardrails AI validators, Llama Guard 3, OpenAI Moderation API
- **Architecture**: Multi-layer: (1) Input rail (jailbreak detection, topic control), (2) Output rail (toxicity, bias, safety classification)
- **Validators**: `detect_jailbreak`, `unusual_prompt`, `toxic_language`, `restrict_to_topic`, `competitor_check`
- **Paper**: "Three-Layer Guardrail for Agentic RAG" (2026 best practices)
- **Input Ports**: `text` (string), `direction` (input/output)
- **Output Ports**: `is_safe` (boolean), `filtered_text` (string), `violations` (list)
- **Config**: `rails` (list: jailbreak/toxicity/bias/topic), `valid_topics` (list), `blocked_topics` (list), `model` (llama_guard/nemo/openai)

### 3.7 `response_formatter` — Response Format Enforcer

- **Purpose**: Enforce structured output format (JSON schema, markdown, bullet points, tables)
- **Libraries**: Instructor, Outlines, Guardrails AI, LMQL
- **Architecture**: Constrained decoding or post-hoc formatting with validation; retry on format failure
- **Input Ports**: `response` (string), `schema` (object)
- **Output Ports**: `formatted_response` (string), `is_valid` (boolean)
- **Config**: `format` (json/markdown/table/bullets), `schema` (JSON Schema), `max_retries` (int), `strict_mode` (bool)

### 3.8 `context_selector` — Selective Context Pruner

- **Purpose**: Select the most relevant context passages and compress/prune irrelevant ones before generation
- **Libraries**: LongLLMLingua, RECOMP, LLMLingua-2
- **Architecture**: Score each passage/sentence for query relevance; keep top-K or compress at target ratio; reduces token costs and "lost in the middle" effects
- **Papers**: "LongLLMLingua" (21.4 point improvement at 4x compression); "RECOMP" (extractive + abstractive compressor); "ACC-RAG" (adaptive compression, 2025); "MacRAG" (multi-scale compression, 2025)
- **Input Ports**: `contexts` (list), `query` (string)
- **Output Ports**: `selected_contexts` (list), `compression_ratio` (float), `token_savings` (integer)
- **Config**: `method` (longllmlingua/recomp/extractive/abstractive), `target_ratio` (float), `max_tokens`, `model_name`

---

## 4. Monitoring & Observability (`monitor`)

### 4.1 `trace_collector` — OpenTelemetry Trace Collector

- **Purpose**: Collect distributed traces across the RAG pipeline (query -> retrieval -> generation -> post-processing)
- **Standard**: OpenTelemetry (OTLP protocol), with semantic conventions for GenAI (OTel GenAI SIG)
- **Architecture**: Instrument each pipeline component as a span; capture latency, token counts, model names, retrieval scores; export to any OTLP backend
- **Backends**: Jaeger, Grafana Tempo, Phoenix (Arize), Langfuse, Datadog
- **Key Spans**: `query_processing`, `retrieval`, `reranking`, `generation`, `post_processing`
- **Input Ports**: `pipeline_event` (object)
- **Output Ports**: `trace_id` (string), `span_data` (object)
- **Config**: `exporter` (otlp/jaeger/console), `endpoint`, `service_name`, `sample_rate` (float), `capture_prompts` (bool)

### 4.2 `quality_scorer` — Real-Time Quality Scorer

- **Purpose**: Score every production response for faithfulness/relevance without blocking the response
- **Architecture**: Async scoring: return response immediately, score in background; store scores for monitoring dashboards; alert on quality degradation
- **Libraries**: RAGAS (async), DeepEval, custom lightweight NLI models
- **Key Feature**: Non-blocking -- scores are computed asynchronously and logged, not used to gate responses
- **Input Ports**: `query` (string), `answer` (string), `contexts` (list)
- **Output Ports**: `scores` (object), `alerts` (list)
- **Config**: `metrics` (list), `alert_thresholds` (object), `scoring_model`, `async_mode` (bool, default true)

### 4.3 `drift_detector` — Embedding & Query Drift Detector

- **Purpose**: Detect semantic drift in embeddings and query patterns that degrade retrieval quality
- **Architecture**: (1) Maintain reference embedding set from probe documents, (2) periodically re-embed probes, (3) compute cosine distance delta; for query drift: cluster production queries and compare distribution over time
- **Detection Methods**: Cosine distance comparison (stable: 0.0001-0.005, drift: >= 0.05), nearest-neighbor stability (stable: 85-95% retention, drift: 25-40% drop), distributional tests (KL divergence, PSI)
- **Libraries**: Evidently AI (5 drift methods), Arize Phoenix, custom implementations
- **Papers**: "Embedding Drift: The Quiet Killer of Retrieval Quality" (2025)
- **Input Ports**: `current_embeddings` (list), `reference_embeddings` (list)
- **Output Ports**: `drift_score` (float), `drift_detected` (boolean), `drift_details` (object)
- **Config**: `method` (cosine/kl_divergence/psi/neighbor_stability), `threshold`, `reference_dataset_path`, `check_interval`

### 4.4 `cost_tracker` — LLM Token & Cost Tracker

- **Purpose**: Track token usage and costs across all LLM calls in the pipeline
- **Architecture**: Intercept every LLM call; log input_tokens, output_tokens, model, cost; aggregate by user, workspace, pipeline, time period
- **Libraries**: Langfuse (built-in cost tracking), LiteLLM (cost per model), Helicone, custom middleware
- **Cost Models**: Per-provider pricing tables; support for cached token discounts; batch API cost tracking
- **Input Ports**: `llm_call_metadata` (object)
- **Output Ports**: `cost_record` (object), `cumulative_cost` (float)
- **Config**: `pricing_table` (object), `budget_limit` (float), `alert_threshold` (float), `aggregation_level` (user/workspace/pipeline)

### 4.5 `latency_monitor` — Pipeline Latency Monitor

- **Purpose**: Track and alert on latency across pipeline stages; identify bottlenecks
- **Architecture**: Measure wall-clock time per component (retrieval, reranking, generation); compute P50/P95/P99; alert on SLA violations; histogram storage
- **Integration**: OpenTelemetry spans, Prometheus metrics, Grafana dashboards
- **Input Ports**: `stage_name` (string), `start_time` (float), `end_time` (float)
- **Output Ports**: `latency_ms` (float), `percentiles` (object), `is_sla_violation` (boolean)
- **Config**: `sla_thresholds_ms` (object by stage), `percentiles` ([50, 95, 99]), `alert_webhook`

### 4.6 `feedback_collector` — User Feedback Collector

- **Purpose**: Collect explicit user feedback (thumbs up/down, ratings, corrections) and correlate with traces
- **Architecture**: Attach feedback to trace_id; store in feedback table; export for evaluation dataset curation and reward model training
- **Libraries**: Langfuse (scores API), custom feedback endpoints
- **Feedback Types**: binary (thumbs up/down), rating (1-5), correction (free text), category (wrong_answer/incomplete/irrelevant/offensive)
- **Input Ports**: `trace_id` (string), `feedback` (object)
- **Output Ports**: `feedback_record` (object), `aggregated_stats` (object)
- **Config**: `feedback_types` (list), `storage_backend` (postgres/redis), `export_format`, `min_feedback_for_alert` (int)

---

## 5. Training & Optimization (`trainer`)

### 5.1 `feedback_aggregator` — Training Data Aggregator

- **Purpose**: Aggregate user feedback, quality scores, and annotation data into training datasets for reward models and policy optimization
- **Architecture**: Join feedback records with (query, context, answer) triples; label as positive/negative; create preference pairs for DPO/RLHF; export in standard formats
- **Paper**: "RAG-Reward: Optimizing RAG with Reward Modeling and RLHF" (arXiv:2501.13264)
- **Input Ports**: `feedback_records` (list), `trace_data` (list)
- **Output Ports**: `training_dataset` (list), `preference_pairs` (list), `statistics` (object)
- **Config**: `min_confidence` (float), `export_format` (jsonl/parquet/hf_dataset), `preference_pair_strategy` (best_vs_worst/pairwise), `filter_criteria`

### 5.2 `reward_model_trainer` — RAG Reward Model Trainer

- **Purpose**: Train reward models that score RAG outputs for hallucination-freedom, completeness, and relevance
- **Architecture**: Fine-tune a classifier on (query, context, answer, score) tuples; use as scoring function for RLHF/DPO optimization of the generator
- **Paper**: "RAG-Reward" (arXiv:2501.13264) -- "enables hallucination-free, comprehensive, reliable, and efficient RAG"
- **Libraries**: `trl` (HuggingFace), `openrlhf`, custom training loops
- **Input Ports**: `training_data` (list), `base_model` (string)
- **Output Ports**: `model_path` (string), `training_metrics` (object)
- **Config**: `base_model`, `learning_rate`, `epochs`, `reward_dimensions` (faithfulness/relevance/completeness), `training_method` (sft/dpo/ppo)

### 5.3 `retrieval_policy_optimizer` — RL-Based Retrieval Policy

- **Purpose**: Train a policy model that decides when/how to retrieve, how many documents to fetch, and when to stop
- **Architecture**: External policy network interacts with RAG pipeline; actions include retrieve/skip/reformulate/stop; trained with PPO/GRPO on downstream answer quality as reward
- **Papers**: "Reinforcement Learning for Optimizing RAG" (arXiv:2401.06800); "RPO: Retrieval Preference Optimization" (arXiv:2501.13726, ICLR 2025)
- **Key Insight**: RL policy optimizes token efficiency -- learns to skip retrieval for simple queries and trigger multi-hop for complex ones
- **Input Ports**: `query` (string), `pipeline_state` (object)
- **Output Ports**: `action` (string), `action_params` (object), `policy_score` (float)
- **Config**: `policy_model`, `action_space` (retrieve/skip/reformulate/decompose/stop), `reward_signal` (answer_quality/cost/latency), `training_method` (ppo/grpo/dpo)

### 5.4 `judge_model_trainer` — LLM Judge Fine-Tuner

- **Purpose**: Fine-tune an LLM to serve as a domain-specific evaluation judge
- **Architecture**: Collect (prompt, response_a, response_b, preference) data; fine-tune using SFT on judge reasoning traces, then DPO on preference pairs; produces a model that outputs structured evaluations
- **Papers**: ARES judge training; "Finetuning LLM Judges" (Cameron Wolfe, 2025 survey); RLAIF / Constitutional AI patterns
- **Methods**: SFT on human-annotated judgments, DPO on preference labels, Judge-wise RL for chain-of-thought reasoning
- **Input Ports**: `training_data` (list), `base_model` (string)
- **Output Ports**: `judge_model_path` (string), `calibration_metrics` (object)
- **Config**: `base_model`, `training_method` (sft/dpo/judge_rl), `evaluation_criteria`, `epochs`, `learning_rate`

### 5.5 `embedding_fine_tuner` — Domain-Specific Embedding Trainer

- **Purpose**: Fine-tune embedding models on domain-specific data for improved retrieval
- **Architecture**: Contrastive learning with InfoNCE loss on (query, positive_passage, hard_negatives); supports sentence-transformers training loop; hard negative mining from existing index
- **Libraries**: `sentence-transformers` v3 (simplified training API), `uniem`, custom training
- **Loss Functions**: InfoNCE, MultipleNegativesRankingLoss, MatryoshkaLoss (for variable-dimension embeddings)
- **Key Result**: Domain fine-tuning with ~5K pairs achieves significant retrieval improvement; ~1 minute on A10G GPU; < $0.10 cost
- **Input Ports**: `training_pairs` (list), `base_model` (string)
- **Output Ports**: `model_path` (string), `evaluation_metrics` (object)
- **Config**: `base_model`, `loss_function` (infonce/mnrl/matryoshka), `epochs`, `batch_size`, `hard_negative_mining` (bool), `evaluation_dataset`

---

## 6. Data Processing & Enrichment (`preprocessor`)

### 6.1 `document_cleaner` — Document Cleaner / Normalizer

- **Purpose**: Clean and normalize raw document text before chunking
- **Operations**: Remove empty lines, extra whitespace, repeated headers/footers, boilerplate, fix encoding issues, normalize Unicode
- **Libraries**: Haystack `DocumentCleaner`, Unstructured `clean` functions, custom regex pipelines
- **Haystack Reference**: `haystack.components.preprocessors.document_cleaner.DocumentCleaner`
- **Input Ports**: `documents` (document_list)
- **Output Ports**: `cleaned_documents` (document_list)
- **Config**: `remove_empty_lines` (bool), `remove_extra_whitespace` (bool), `remove_repeated_substrings` (bool), `remove_regex` (string), `unicode_normalization` (NFC/NFKC), `min_doc_length` (int)

### 6.2 `table_extractor` — Table Structure Extractor

- **Purpose**: Extract tables from PDFs/images preserving row/column/header structure
- **Libraries**: Docling `TableFormer`, Unstructured table extraction (VLM-based), `camelot`, `tabula-py`, `pdfplumber`
- **Architecture**: (1) Detect table regions via layout analysis, (2) Extract cell content and structure, (3) Output as HTML/Markdown/JSON preserving relationships
- **Key Feature**: Multi-level header support; merged cell handling; GPU-accelerated extraction
- **Input Ports**: `documents` (document_list)
- **Output Ports**: `tables` (list), `table_metadata` (list)
- **Config**: `engine` (docling/unstructured/camelot/pdfplumber), `output_format` (html/markdown/json/csv), `ocr_enabled` (bool), `gpu_accelerated` (bool)

### 6.3 `image_processor` — Image & Chart Processor

- **Purpose**: Extract information from images, charts, diagrams, and figures in documents
- **Architecture**: (1) Detect image regions via layout analysis, (2) Send to VLM (GPT-4V, Claude Vision, Gemini) for description generation, (3) Output searchable text descriptions alongside original images
- **Libraries**: Unstructured image processing, Docling, LlamaIndex multimodal
- **Use Cases**: Chart data extraction, diagram understanding, figure caption generation, infographic parsing
- **Input Ports**: `images` (list), `image_metadata` (list)
- **Output Ports**: `descriptions` (string_list), `extracted_data` (list)
- **Config**: `vlm_provider` (openai/anthropic/google), `description_detail` (brief/detailed), `extract_data_points` (bool), `output_format`

### 6.4 `metadata_enricher` — AI-Powered Metadata Enricher

- **Purpose**: Automatically generate rich metadata (topics, entities, summaries, keywords, sentiment) for documents
- **Architecture**: LLM-based extraction of semantic tags, named entities, document type, language, topic classification, key phrases; stored as filterable metadata
- **Libraries**: Haystack `MetadataEnricher`, custom LLM-based pipelines
- **Haystack Reference**: Advanced RAG technique for improving retrieval precision
- **Input Ports**: `documents` (document_list)
- **Output Ports**: `enriched_documents` (document_list)
- **Config**: `enrichments` (list: topics/entities/summary/keywords/sentiment/language/doc_type), `llm_provider`, `max_keywords` (int), `entity_types` (list)

### 6.5 `language_detector` — Language Detection

- **Purpose**: Detect the language of documents and route to appropriate processing pipelines
- **Libraries**: `fasttext` (lid.176), `langdetect`, `lingua-py`, `pycld3`
- **Architecture**: Classify document/chunk language; optionally route to language-specific embedders/generators; support for multilingual detection in mixed-language documents
- **Input Ports**: `text` (string)
- **Output Ports**: `language` (string), `confidence` (float), `all_languages` (list)
- **Config**: `method` (fasttext/langdetect/lingua), `min_confidence` (float), `supported_languages` (list)

### 6.6 `deduplicator` — Near-Duplicate Document Detector

- **Purpose**: Detect and remove duplicate or near-duplicate documents/chunks from the corpus
- **Architecture**: (1) Exact: hash-based (MD5/SHA256), (2) Near-duplicate: MinHash + LSH with configurable Jaccard threshold, (3) Semantic: embedding cosine similarity
- **Libraries**: `datasketch` (MinHash/LSH), Milvus 2.6 (native MinHash LSH), `galactic`, LSHBloom (12x faster than MinHashLSH)
- **Papers**: "LSHBloom: Internet-Scale Text Deduplication" (arXiv:2411.04257, 2025)
- **Input Ports**: `documents` (document_list)
- **Output Ports**: `unique_documents` (document_list), `duplicates` (list), `dedup_stats` (object)
- **Config**: `method` (exact/minhash/semantic), `threshold` (float), `num_perm` (int, for MinHash), `shingle_size` (int)

### 6.7 `equation_extractor` — Math/Equation Extractor

- **Purpose**: Extract and convert mathematical equations from documents to LaTeX/MathML
- **Libraries**: Docling (planned), Nougat (Meta), `pix2tex`, MathPix API
- **Architecture**: Detect equation regions via layout analysis; OCR/VLM to LaTeX conversion; embed LaTeX as searchable text
- **Input Ports**: `documents` (document_list)
- **Output Ports**: `equations` (list), `latex_strings` (string_list)
- **Config**: `engine` (nougat/pix2tex/mathpix), `output_format` (latex/mathml), `inline_detection` (bool)

---

## 7. Export & Deployment (`deployment`)

### 7.1 `pipeline_serializer` — Pipeline Serializer/Deserializer

- **Purpose**: Serialize a pipeline definition to YAML/JSON for storage, versioning, and portability
- **Architecture**: Each component implements `to_dict()` / `from_dict()`; pipeline graph serialized as nodes + edges + component configs; support callbacks during deserialization for migration
- **Reference**: Haystack serialization (`dumps()`/`loads()` to YAML/TOML), LlamaIndex pipeline serialization
- **Input Ports**: `pipeline` (object)
- **Output Ports**: `serialized` (string), `format` (string)
- **Config**: `format` (yaml/json/toml), `include_defaults` (bool), `version` (string), `validate_on_load` (bool)

### 7.2 `llm_provider_adapter` — Universal LLM Provider Adapter

- **Purpose**: Unified interface to 100+ LLM providers via LiteLLM
- **Library**: LiteLLM (Python SDK + Proxy Server)
- **Providers**: OpenAI, Anthropic, Google (Gemini), Azure, AWS Bedrock, Cohere, Mistral, Ollama, vLLM, HuggingFace, Groq, Together, Replicate, and 90+ more
- **Features**: Automatic provider routing, load balancing (simple-shuffle, least-busy, latency-based, usage-based), fallbacks with retry logic, cost tracking per model, 8ms P95 latency at 1K RPS
- **Input Ports**: `prompt` (string), `model` (string)
- **Output Ports**: `response` (string), `usage` (object), `cost` (float)
- **Config**: `model_list` (list of deployments), `routing_strategy` (simple_shuffle/least_busy/latency_based/usage_based), `fallback_models` (list), `num_retries`, `timeout`, `api_keys`

### 7.3 `api_endpoint_generator` — Auto REST Endpoint Generator

- **Purpose**: Automatically expose a pipeline as a REST API with OpenAPI documentation
- **Architecture**: Takes a compiled pipeline; generates FastAPI routes with request/response schemas derived from pipeline input/output ports; includes health check, async execution, and streaming endpoints
- **Input Ports**: `pipeline_definition` (object)
- **Output Ports**: `api_spec` (object), `endpoint_url` (string)
- **Config**: `base_path` (string), `auth_required` (bool), `rate_limit` (int), `enable_streaming` (bool), `enable_async` (bool), `cors_origins` (list)

### 7.4 `health_check_endpoint` — Pipeline Health Check

- **Purpose**: Expose liveness, readiness, and startup probes for Kubernetes deployment
- **Architecture**: Liveness (`/healthz`) -- is the process alive; Readiness (`/ready`) -- are all dependencies (DB, vector store, LLM) reachable; Startup (`/startup`) -- has initial model loading completed
- **Checks**: Database connectivity, vector store ping, LLM provider reachability, Redis connectivity, model loading status
- **Input Ports**: (none -- event-driven)
- **Output Ports**: `status` (string), `checks` (object), `timestamp` (string)
- **Config**: `check_dependencies` (list: db/vector_store/llm/redis/model), `startup_timeout_s` (int), `liveness_path`, `readiness_path`

### 7.5 `docker_packager` — Pipeline Docker Packager

- **Purpose**: Package a pipeline definition + dependencies into a deployable Docker image
- **Architecture**: Generate Dockerfile from pipeline components; resolve Python dependencies; build multi-stage image with minimal runtime; include health checks and configuration
- **Input Ports**: `pipeline_definition` (object), `requirements` (list)
- **Output Ports**: `dockerfile` (string), `image_tag` (string)
- **Config**: `base_image`, `python_version`, `gpu_enabled` (bool), `registry_url`, `include_models` (bool)

---

## 8. Caching (`cache`) -- New Category

### 8.1 `semantic_cache` — Semantic Query Cache

- **Purpose**: Cache responses for semantically similar queries to reduce LLM calls and latency
- **Architecture**: Embed incoming query; search cache index for similar queries above threshold; return cached response if match found; otherwise execute pipeline and cache result
- **Libraries**: GPTCache, Redis Vector Search, custom embedding similarity cache
- **Key Metric**: Typically 20-40% cache hit rate in production; reduces average latency by 60-80% on hits
- **Input Ports**: `query` (string), `query_embedding` (list)
- **Output Ports**: `cached_response` (string, nullable), `cache_hit` (boolean), `similarity_score` (float)
- **Config**: `similarity_threshold` (float, default 0.95), `ttl_seconds` (int), `max_cache_size`, `embedding_model`, `backend` (redis/faiss/qdrant)

### 8.2 `result_cache` — Retrieval Result Cache

- **Purpose**: Cache retrieval results (chunks) for repeated or similar queries
- **Architecture**: Hash-based caching of (query_hash -> retrieved_chunks); TTL-based expiration; invalidation on index update
- **Input Ports**: `query` (string), `retriever_config` (object)
- **Output Ports**: `cached_chunks` (list, nullable), `cache_hit` (boolean)
- **Config**: `ttl_seconds` (int), `max_entries`, `invalidation_strategy` (ttl/on_index_update), `backend` (redis/memory)

---

## 9. Conversation (`conversation`) -- New Category

### 9.1 `conversation_memory` — Conversation History Manager

- **Purpose**: Maintain conversation context across multi-turn interactions
- **Architecture**: Store message history with sliding window; support for summary-based compression of older messages; entity memory for tracking mentioned entities
- **Types**: Buffer (last N messages), Summary (LLM-summarized history), Entity (extracted entity tracking), Vector (semantically searchable history)
- **Input Ports**: `message` (string), `session_id` (string)
- **Output Ports**: `context` (string), `history` (list), `entities` (object)
- **Config**: `memory_type` (buffer/summary/entity/vector), `max_messages` (int), `summary_model`, `session_ttl_hours`

### 9.2 `query_rewriter` — Conversational Query Rewriter

- **Purpose**: Rewrite queries in conversational context to be self-contained (resolve pronouns, incorporate context)
- **Architecture**: Takes current query + conversation history; LLM rewrites to standalone query suitable for retrieval; handles coreference resolution and context injection
- **Input Ports**: `query` (string), `history` (list)
- **Output Ports**: `rewritten_query` (string), `is_followup` (boolean)
- **Config**: `model`, `max_history_turns` (int), `include_entities` (bool)

---

## 10. Connector (`connector`) -- New Category

### 10.1 `database_connector` — SQL/NoSQL Database Connector

- **Purpose**: Connect to structured databases for text-to-SQL or hybrid retrieval
- **Architecture**: Schema introspection; LLM-based natural language to SQL; execute query; format results as context
- **Databases**: PostgreSQL, MySQL, SQLite, MongoDB, Snowflake, BigQuery
- **Input Ports**: `query` (string), `connection_config` (object)
- **Output Ports**: `results` (list), `sql_query` (string), `schema` (object)
- **Config**: `connection_string`, `allowed_tables` (list), `max_rows` (int), `read_only` (bool)

### 10.2 `api_connector` — External API Connector

- **Purpose**: Fetch real-time data from external REST APIs as context for RAG
- **Architecture**: Configurable HTTP client; LLM generates API parameters from natural language; response parsing and context injection
- **Input Ports**: `query` (string), `api_spec` (object)
- **Output Ports**: `api_response` (object), `formatted_context` (string)
- **Config**: `base_url`, `auth_type` (api_key/oauth/bearer), `rate_limit`, `timeout`, `response_path` (JSONPath)

### 10.3 `knowledge_base_sync` — Knowledge Base Synchronizer

- **Purpose**: Keep RAG index in sync with upstream data sources (S3, SharePoint, Confluence, Google Drive, etc.)
- **Architecture**: Change detection (polling/webhook/CDC); differential indexing (add/update/delete); supports incremental re-indexing
- **Connectors**: S3, GCS, Azure Blob, SharePoint, Confluence, Notion, Google Drive, GitHub, Slack
- **Input Ports**: `source_config` (object), `sync_state` (object)
- **Output Ports**: `changes` (list), `new_sync_state` (object), `sync_stats` (object)
- **Config**: `source_type`, `poll_interval_minutes`, `change_detection` (polling/webhook/cdc), `include_patterns`, `exclude_patterns`

---

## Summary: Proposed Expansion

### New Components by Category

| Category | Status | New Components | Total |
|----------|--------|---------------|-------|
| **parser** | existing | 0 | 3 |
| **chunker** | existing | 0 | 8 |
| **embedder** | existing | 0 | 9 |
| **extractor** | existing | 0 | 4 |
| **retriever** | existing | 0 | 7 |
| **reranker** | existing | 0 | 5 |
| **generator** | existing | 0 | 3 |
| **indexer** | existing | 0 | 2 |
| **storage** | existing | 0 | 3 |
| **graph_builder** | existing | 0 | 2 |
| **planner** | existing | 0 | 3 |
| **agent** | existing | 0 | 9 |
| **evaluation** | **NEW** | 7 | 7 |
| **orchestrator** | **NEW** | 6 | 6 |
| **guardrail** | **NEW** | 8 | 8 |
| **monitor** | **NEW** | 6 | 6 |
| **trainer** | **NEW** | 5 | 5 |
| **preprocessor** | **NEW** | 7 | 7 |
| **deployment** | **NEW** | 5 | 5 |
| **cache** | **NEW** | 2 | 2 |
| **conversation** | **NEW** | 2 | 2 |
| **connector** | **NEW** | 3 | 3 |
| **TOTAL** | | **51 new** | **109** |

### Category Count: 22 categories (12 existing + 10 new)

---

## Key Libraries & Tools Reference

| Library | Category | Purpose | License |
|---------|----------|---------|---------|
| [RAGAS](https://github.com/explodinggradients/ragas) | evaluation | Reference-free RAG evaluation | Apache 2.0 |
| [DeepEval](https://github.com/confident-ai/deepeval) | evaluation | Pytest-compatible LLM testing | Apache 2.0 |
| [ARES](https://github.com/stanford-futuredata/ARES) | evaluation | Automated RAG eval with PPI | MIT |
| [Langfuse](https://github.com/langfuse/langfuse) | monitor | Open-source LLM observability | MIT |
| [Phoenix (Arize)](https://github.com/Arize-ai/phoenix) | monitor | LLM tracing & evaluation | Elastic 2.0 |
| [LiteLLM](https://github.com/BerriAI/litellm) | deployment | Unified LLM API gateway | MIT |
| [Presidio](https://github.com/microsoft/presidio) | guardrail | PII detection & anonymization | MIT |
| [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) | guardrail | Programmable LLM guardrails | Apache 2.0 |
| [Guardrails AI](https://github.com/guardrails-ai/guardrails) | guardrail | Input/output validation | Apache 2.0 |
| [LongLLMLingua](https://github.com/microsoft/LLMLingua) | guardrail | Prompt compression | MIT |
| [Docling](https://github.com/DS4SD/docling) | preprocessor | Document AI (IBM) | MIT |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | preprocessor | Document processing | Apache 2.0 |
| [Sentence Transformers](https://github.com/UKPLab/sentence-transformers) | trainer | Embedding fine-tuning | Apache 2.0 |
| [TRL](https://github.com/huggingface/trl) | trainer | RLHF/DPO training | Apache 2.0 |
| [Evidently AI](https://github.com/evidentlyai/evidently) | monitor | ML monitoring & drift | Apache 2.0 |
| [GPTCache](https://github.com/zilliztech/GPTCache) | cache | Semantic caching | MIT |
| [datasketch](https://github.com/ekzhu/datasketch) | preprocessor | MinHash/LSH deduplication | MIT |
| [Instructor](https://github.com/jxnl/instructor) | guardrail | Structured LLM output | MIT |
| [Outlines](https://github.com/outlines-dev/outlines) | guardrail | Constrained generation | Apache 2.0 |
| [ranx](https://github.com/AmenRa/ranx) | evaluation | IR metric computation | MIT |

---

## Key Papers Reference

| Paper | Year | Relevance |
|-------|------|-----------|
| RAGAS: Automated Evaluation of RAG | 2023/2025 | Foundational RAG evaluation framework |
| ARES: Automated RAG Evaluation System | 2024 | Fine-tuned judge + PPI for confident scoring |
| Self-RAG: Learning to Retrieve, Generate, and Critique | 2024 | Self-correction with reflection tokens |
| CRAG: Corrective RAG | 2024 | Retrieval quality assessment + web fallback |
| RAG-Reward: Optimizing RAG with Reward Modeling | 2025 | RLHF for hallucination-free RAG |
| RPO: Retrieval Preference Optimization | 2025 (ICLR) | DPO-style retrieval optimization |
| FACTUM: Mechanistic Citation Hallucination Detection | 2026 | Internal pathway analysis for citation verification |
| MetaRAG: Metamorphic Testing for Hallucination | 2025 | Atomic factoid mutation-based detection |
| HalluGraph: Auditable Hallucination Detection | 2025 | Graph-based grounding for legal RAG |
| ReClaim: Fine-Grained Attribution | 2024 | 90% citation accuracy at sentence level |
| GaRAGe: Grounding Annotations for RAG | 2025 | Large-scale grounding benchmark |
| LongLLMLingua | 2024 | 21.4pt improvement at 4x compression |
| RECOMP: Compressing Retrieved Documents | 2024 | Extractive + abstractive compression |
| ACC-RAG: Adaptive Context Compression | 2025 | Dynamic compression rates |
| MacRAG: Multi-Scale Adaptive Context | 2025 | Offline chunk compression |
| LSHBloom: Internet-Scale Deduplication | 2025 | 12x faster than MinHashLSH |
| Know Your RAG: Dataset Taxonomy | 2024 | Synthetic evaluation dataset strategies |
| Docling Technical Report | 2024/2025 | Document AI for table/layout extraction |
| Three-Layer Guardrail for Agentic RAG | 2026 | Input/process/output guardrail pattern |
| Embedding Drift: Quiet Killer of Retrieval Quality | 2025 | Drift detection methods for RAG |
| Adaptive-RAG | 2024 | Query complexity-based retrieval routing |

---

## Architectural Patterns

### Pattern 1: Three-Layer Guardrail Architecture
```
Input Layer  -->  Process Layer  -->  Output Layer
(jailbreak,      (retrieval        (hallucination,
 PII filter,      validation,       citation check,
 topic control)   context check)    toxicity filter)
```

### Pattern 2: Evaluate-Then-Train Loop
```
Production Traffic
    |
    v
Quality Scorer (async) --> Feedback Collector
    |                          |
    v                          v
Drift Detector            Feedback Aggregator
    |                          |
    v                          v
Alert / Retrain       Reward Model Trainer
                           |
                           v
                    Policy Optimizer
                           |
                           v
                    Updated Pipeline
```

### Pattern 3: A/B Testing Pipeline
```
Query --> A/B Splitter --> Variant A Pipeline --> Response A
                      \--> Variant B Pipeline --> Response B
                                                     |
                                               Quality Scorer
                                                     |
                                               Metrics Dashboard
```

### Pattern 4: Self-Correcting RAG Loop
```
Query --> Retrieve --> Generate --> Self-Critique
                                       |
                              [Good enough?]
                              /           \
                           Yes             No
                            |               |
                        Return          Reformulate Query
                                            |
                                        Re-Retrieve
                                            |
                                        Re-Generate
                                            |
                                       (loop max N)
```

### Pattern 5: Multi-Agent Coordination
```
Supervisor Agent
    |
    +--> Retriever Agent (dense/sparse/graph selection)
    |
    +--> Reasoner Agent (multi-hop, decomposition)
    |
    +--> Fact-Checker Agent (hallucination, grounding)
    |
    +--> Formatter Agent (citations, structure)
    |
    v
Aggregated Response
```

---

## Implementation Priority

### Phase 1 (High Impact, Low Complexity)
1. `document_cleaner` -- essential preprocessing
2. `pii_filter` -- compliance requirement
3. `hallucination_detector` -- quality critical
4. `citation_generator` -- trust building
5. `cost_tracker` -- operational necessity
6. `feedback_collector` -- data flywheel
7. `semantic_cache` -- latency/cost reduction
8. `llm_provider_adapter` -- provider flexibility

### Phase 2 (High Impact, Medium Complexity)
9. `ragas_evaluator` -- evaluation baseline
10. `deepeval_evaluator` -- CI/CD integration
11. `trace_collector` -- observability foundation
12. `safety_filter` -- safety requirement
13. `intent_classifier` -- routing efficiency
14. `query_rewriter` -- conversational UX
15. `deduplicator` -- data quality
16. `metadata_enricher` -- retrieval improvement

### Phase 3 (Medium Impact, Higher Complexity)
17. `self_correction_agent` -- answer quality
18. `drift_detector` -- proactive monitoring
19. `benchmark_generator` -- systematic evaluation
20. `context_selector` -- cost optimization
21. `answer_validator` -- output quality gate
22. `pipeline_serializer` -- deployment workflow
23. `table_extractor` -- document handling
24. `image_processor` -- multimodal support

### Phase 4 (Strategic, High Complexity)
25. `multi_agent_coordinator` -- advanced orchestration
26. `strategy_selector` -- adaptive retrieval
27. `embedding_fine_tuner` -- domain optimization
28. `reward_model_trainer` -- training pipeline
29. `retrieval_policy_optimizer` -- RL optimization
30. `judge_model_trainer` -- evaluation improvement
