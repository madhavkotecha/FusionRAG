# RAG Evaluation & Benchmarking Frameworks: Technical Research Notes

**Date**: March 2026
**Scope**: Comprehensive survey of RAG evaluation frameworks, benchmarks, metrics, and recent papers (2023-2026)

---

## 1. Major RAG Evaluation Frameworks

### 1.1 RAGAS (Retrieval Augmented Generation Assessment)

**Paper**: Es et al., "Ragas: Automated Evaluation of Retrieval Augmented Generation" (EACL 2024 Demo, arXiv:2309.15217)
**Repo**: https://github.com/explodinggradients/ragas
**License**: Apache 2.0

**Core Concept**: Reference-free evaluation of RAG pipelines using LLM-as-judge. Pioneered automated RAG eval without human annotations. De facto standard in the field.

**Metrics Provided** (as of v0.2.x):

| Category | Metric | What It Measures |
|---|---|---|
| RAG - Retrieval | Context Precision | Relevance of retrieved chunks; penalizes irrelevant chunks ranked higher |
| RAG - Retrieval | Context Recall | Whether retrieved context covers all claims in the reference answer |
| RAG - Retrieval | Context Entities Recall | Entity-level overlap between retrieved context and reference |
| RAG - Retrieval | Noise Sensitivity | Robustness to irrelevant context mixed into retrieval results |
| RAG - Generation | Faithfulness | Fraction of response claims supported by retrieved context |
| RAG - Generation | Response Relevancy | Relevance of generated answer to the input query |
| RAG - Multimodal | Multimodal Faithfulness | Faithfulness for image/video content |
| RAG - Multimodal | Multimodal Relevance | Relevance for multimodal outputs |
| NL Comparison | Factual Correctness | Factual accuracy vs. ground truth |
| NL Comparison | Semantic Similarity | Embedding-based similarity to reference |
| NL Comparison | BLEU, ROUGE, CHRF | Traditional n-gram overlap metrics |
| NL Comparison | Answer Correctness | Weighted combo of semantic + factual similarity |
| General Purpose | Aspect Critic | Binary pass/fail on user-defined aspects (harmfulness, coherence, etc.) |
| General Purpose | Rubrics-based Scoring | Likert-scale scoring with custom rubrics |
| General Purpose | Simple Criteria Scoring | Score on a single user-defined criterion |
| Agent/Tool | Tool Call Accuracy | Correctness of tool invocations |
| Agent/Tool | Agent Goal Accuracy | Whether agent achieved its goal |
| Agent/Tool | Topic Adherence | Whether agent stayed on topic |
| SQL | Datacompy Score | Execution-based SQL equivalence |
| NVIDIA | Answer Accuracy, Context Relevance, Response Groundedness | Pre-built NVIDIA NeMo evaluators |

**Key Features**:
- Synthetic test generation using evolution-based paradigms (reduces manual curation by ~90%)
- Supports both LLM-based and traditional metrics
- HHEM-2.1-Open integration for hallucination detection
- Metric training/alignment to customize judges for specific domains

**Known Limitations**:
- NaN scores when LLM judge returns invalid JSON (no graceful fallback)
- No built-in observability, experiment tracking, or production monitoring
- Typically paired with other tools (LangSmith, Phoenix) for full workflow

---

### 1.2 DeepEval (by Confident AI)

**Repo**: https://github.com/confident-ai/deepeval
**License**: Apache 2.0

**Core Concept**: Pytest-like unit testing framework for LLM applications. 50+ out-of-the-box metrics. Debuggable LLM judge decisions.

**RAG-Specific Metrics**:

| Metric | Description |
|---|---|
| Faithfulness | Whether output factually aligns with retrieval context |
| Contextual Recall | Whether all ground-truth claims are present in retrieved context |
| Contextual Precision | Whether most relevant chunks are ranked highest |
| Contextual Relevancy | Whether retrieved context is relevant to the input |
| Answer Relevancy | Whether output is relevant to the user input |
| RAGAS (composite) | Average of answer relevancy, faithfulness, contextual precision, contextual recall |
| Hallucination | Detection of unsupported claims in output |
| Summarization | Quality of summarization tasks |

**Additional Capabilities**:
- **Multi-turn RAG evaluation**: `ConversationalTestCase` with sliding window approach for conversation-level retrieval quality
- **Agentic metrics**: Task Completion (LLM tracing to score if agent resolves inferred goal), Tool Correctness
- **Red-teaming metrics**: Bias, toxicity, prompt injection detection
- **Custom metric builder**: Define domain-specific evaluation criteria
- **Debuggable judgments**: Inspect LLM judge reasoning step by step

**Key Differentiator**: All metrics are debuggable -- you can inspect the LLM judge's intermediate judgments to understand why a score was assigned.

---

### 1.3 ARES (Automated RAG Evaluation System)

**Paper**: Saad-Falcon et al., "ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems" (arXiv:2311.09476)
**Repo**: https://github.com/stanford-futuredata/ARES

**Core Concept**: Finetunes lightweight LM judges instead of using expensive LLM-as-judge. Uses Prediction-Powered Inference (PPI) to calibrate with minimal human annotations.

**Three Evaluation Dimensions**:
1. **Context Relevance**: Is the retrieved context relevant to the query?
2. **Answer Faithfulness**: Is the answer grounded in the retrieved context?
3. **Answer Relevance**: Does the answer address the query?

**Methodology**:
1. Generate synthetic training data (query, passage, answer triples)
2. Finetune DeBERTa-v3-large (437M params) with 3 classification heads (one per dimension)
3. Use PPI with a small set (~150-300) of human annotations to calibrate predictions
4. Evaluate RAG system outputs

**Performance**: Finetuned DeBERTa judges significantly outperform zero-shot and few-shot GPT-3.5-turbo-16k judges. Validated across 8 knowledge-intensive tasks (KILT, SuperGLUE, AIS).

**Key Differentiator**: Much cheaper than LLM-as-judge at inference time. Robust to domain shifts.

---

### 1.4 TruLens (by Snowflake/TruEra)

**Repo**: https://github.com/truera/trulens
**Website**: https://www.trulens.org/

**Core Concept**: The "RAG Triad" -- three fundamental metrics that together ensure hallucination-free RAG. Now integrated with OpenTelemetry for production observability.

**The RAG Triad**:

| Metric | Definition | Why It Matters |
|---|---|---|
| Context Relevance | Each retrieved chunk is relevant to the input query | Irrelevant context can be woven into hallucinations |
| Groundedness | Generated answer is supported by the retrieved context | Catches LLM tendency to exaggerate or expand beyond facts |
| Answer Relevance | Generated answer addresses the original query | Sanity check that the system produces helpful output |

**2025 Updates**:
- OpenTelemetry (OTel) support for vendor-agnostic observability
- Agent evaluation framework: evaluates alignment of agent's goal, plan, and actions
- Benchmarked on TRAIL dataset -- covers 95% of internal agent errors
- Reference-free agent metrics that review traces and identify improvements
- Benchmarks used: LLM-AggreFact, TREC-DL, HotPotQA

---

### 1.5 RAGChecker (by Amazon Science)

**Paper**: NeurIPS 2024 Datasets & Benchmarks Track (arXiv:2408.08067)
**Repo**: https://github.com/amazon-science/RAGChecker

**Core Concept**: Fine-grained claim-level entailment checking. Decomposes responses into individual claims and checks each against context/ground truth.

**Metrics Suite**:

| Category | Metric | Description |
|---|---|---|
| Overall | Precision | Fraction of generated claims that are correct |
| Overall | Recall | Fraction of ground-truth claims covered by response |
| Overall | F1 | Harmonic mean of precision and recall |
| Retriever | Claim Recall | Whether retrieved context covers claims needed for the answer |
| Retriever | Context Precision | Relevance of retrieved documents to the query |
| Generator | Context Utilization | How effectively the generator uses relevant retrieved info |
| Generator | Noise Sensitivity (relevant) | Robustness when irrelevant info mixed with relevant content |
| Generator | Noise Sensitivity (irrelevant) | Performance on purely irrelevant retrieved material |
| Generator | Hallucination | Content generated without support from retrieved context |
| Generator | Self-Knowledge | Reliance on model's internal knowledge vs. retrieved context |
| Generator | Faithfulness | Overall adherence of response to source material |

**Meta-Evaluation Result**: Significantly higher correlation with human judgments than other evaluation metrics (RAGAS, BERTScore, etc.).

**Evaluation Scale**: Tested on 4,162 queries across 10 domains, with 8 RAG systems (2 retrievers x 4 generators).

---

### 1.6 Giskard (RAGET)

**Repo**: https://github.com/Giskard-AI/giskard-oss
**Website**: https://www.giskard.ai/

**Core Concept**: Umbrella AI testing platform with RAG Evaluation Toolkit (RAGET). Focuses on both business failures (hallucinations, factual errors) and security failures (prompt injection, stereotypes).

**Capabilities**:
- Auto-generates comprehensive test sets from knowledge bases
- Evaluates RAG across multiple dimensions (correctness, grounding, source attribution)
- Detects security vulnerabilities via adversarial synthetic test cases
- Detects business failures (hallucination, denial to answer) via document-based queries
- Integrates with MLflow for experiment tracking

**Key Differentiator**: Unlike RAGAS (specialized metrics tool), Giskard is a full testing platform covering security + business logic + RAG quality. Teams often use RAGAS for detailed QA metrics and Giskard for broader safety scans.

---

### 1.7 UpTrain

**Repo**: https://github.com/uptrain-ai/uptrain

**Core Concept**: Open-source observability and evaluation tool for production LLM monitoring. 20+ predefined metrics with drift detection and root-cause analysis.

**Metrics**: Context relevance, factual accuracy, response completeness, guideline adherence, hallucination detection, custom critique-based scoring.

**Key Differentiator**: Rapid deployment, production monitoring focus, versioned prompt tracking, collaborative debugging.

---

### 1.8 Cleanlab TLM (Trustworthy Language Model)

**Website**: https://cleanlab.ai/
**Paper**: Cleanlab, 2024

**Core Concept**: Wrapper on any base LLM that scores trustworthiness of every response in real-time using uncertainty estimation (self-reflection + consistency across sampled responses + probabilistic measures).

**Evaluation Scores** (each 0-1):
- `context_sufficiency` -- Is the context sufficient to answer the query?
- `response_groundedness` -- Is the response grounded in context?
- `response_helpfulness` -- Is the response helpful?
- `trustworthiness` -- Overall trustworthiness score

**Performance Claims**:
- Detects incorrect RAG responses with 3x greater precision than RAGAS groundedness/faithfulness scores
- Highest precision/recall for hallucination detection across 4 RAG benchmarks compared to LLM-as-a-judge and other methods
- No custom-trained model required (uses any LLM, including latest frontier models)

---

### 1.9 Vectara Open RAG Eval

**Repo**: https://github.com/vectara/open-rag-eval
**Released**: April 2025

**Core Concept**: Reference-free RAG evaluation -- no "golden answers" required. Uses UMBRELA scoring and HHEM for hallucination detection.

**Metrics**:
- **UMBRELA Score**: 0-3 scale for search result quality (reference-free)
- **HHEM Factuality Score**: 0-1 scale using Hughes Hallucination Evaluation Model (0=fully hallucinated, 1=fully factual)
- **Consistency-Adjusted Index** (added July 2025): Evaluates both quality and consistency of responses across repeated queries

**Key Differentiator**: No golden chunks or golden answers needed. Developed with University of Waterloo researchers.

---

### 1.10 Arize Phoenix

**Repo**: https://github.com/Arize-ai/phoenix
**License**: Elastic License 2.0

**Core Concept**: Open-source AI observability platform built on OpenTelemetry. Production monitoring + evaluation for RAG/LLM apps.

**Features**:
- Pre-built evaluators for hallucination, relevance, correctness, RAG-specific metrics
- Built-in concurrency and batching (up to 20x speedup in evaluation)
- Vendor-agnostic (supports LlamaIndex, LangChain, Haystack, DSPy)
- Tracing + evaluation + troubleshooting in one platform

---

## 2. Standard RAG Benchmarks

### 2.1 BEIR (Benchmarking Information Retrieval)

**Paper**: Thakur et al., NeurIPS 2021
**Focus**: Zero-shot retrieval evaluation across diverse domains

| Aspect | Detail |
|---|---|
| Datasets | 18 datasets across 9 task types |
| Tasks | Fact checking, question answering, duplicate detection, citation prediction, argument retrieval, forum retrieval |
| What It Tests | Retriever generalization -- can a model trained on one domain retrieve well on another? |
| Key Use | Evaluating embedding models and retrievers in domain-agnostic settings |

---

### 2.2 KILT (Knowledge Intensive Language Tasks)

**Paper**: Petroni et al., NAACL 2021
**Focus**: End-to-end evaluation of knowledge-intensive NLP tasks grounded in Wikipedia

| Aspect | Detail |
|---|---|
| Datasets | Natural Questions (NQ), HotpotQA, FEVER, Wizard of Wikipedia (WoW), T-REx, etc. |
| Tasks | Fact verification, entity linking, slot filling, open-domain QA, dialogue |
| What It Tests | End-to-end retrieval + generation on Wikipedia-grounded tasks |
| Key Use | Standard benchmark for RAG system comparison; used by ARES for validation |

---

### 2.3 RGB (Retrieval-Augmented Generation Benchmark)

**Paper**: Chen et al., 2024 (arXiv:2309.01431)
**Focus**: Testing 4 fundamental LLM abilities required for RAG

| Ability | Definition | Metric |
|---|---|---|
| Noise Robustness | Handle irrelevant/misleading info without quality loss | Misleading Rate, Mistake Reappearance Rate |
| Negative Rejection | Withhold response when context is insufficient | Rejection Rate |
| Information Integration | Synthesize info from multiple retrieved passages | Accuracy on multi-passage questions |
| Counterfactual Robustness | Identify and disregard incorrect context | Error Detection Rate |

**Dataset**: Constructed from recent news reports with LLM-generated events, questions, and answers. Available in English and Chinese.

---

### 2.4 CRUD-RAG

**Paper**: Lyu et al., ACM Transactions on Information Systems, 2024
**Focus**: Categorizes RAG tasks into CRUD database operations

| Operation | RAG Task | What It Tests |
|---|---|---|
| Create | Generating new content based on retrieved info | Creative synthesis from context |
| Read | Extracting/reading information from context | Direct information extraction |
| Update | Modifying/updating existing information | Ability to revise based on new context |
| Delete | Filtering out irrelevant information | Noise filtering and negative rejection |

**Language**: Chinese-focused benchmark.

---

### 2.5 RAGBench + TRACe Framework

**Paper**: Friel et al., 2024 (arXiv:2407.11005)
**Focus**: First large-scale RAG benchmark with explainable metrics

| Aspect | Detail |
|---|---|
| Scale | 100,000 examples from industry corpora (user manuals, etc.) |
| Framework | TRACe -- Utilization, Relevance, Adherence, Completeness |
| Annotations | Token-level labels for utilization and relevance |

**TRACe Metrics**:

| Metric | Measures | Target |
|---|---|---|
| **Utilization** | Fraction of retrieved context actually used by the generator | Generator quality |
| **Relevance** | Whether context contains specific info needed (beyond semantic similarity) | Retriever quality |
| **Adherence** | How well output adheres to factual source info (= faithfulness/groundedness) | Generator quality |
| **Completeness** | Whether response incorporates all relevant info from context | Generator quality |

**Key Finding**: Finetuned RoBERTa outperforms LLM-based RAG evaluation methods on TRACe metrics, suggesting small specialized models can be more reliable evaluators.

---

### 2.6 MultiHop-RAG

**Paper**: Tang et al., 2024 (OpenReview)
**Focus**: Multi-hop reasoning over RAG

| Aspect | Detail |
|---|---|
| Knowledge Base | English news articles |
| Query Types | Multi-hop queries requiring reasoning across multiple documents |
| Components | Knowledge base + multi-hop queries + ground-truth answers + supporting evidence |
| What It Tests | Ability to perform multi-step retrieval and reasoning |

---

### 2.7 CRAG (Comprehensive RAG Benchmark)

**Paper**: Yang et al. (Meta), 2024 (arXiv:2406.04744)
**Competition**: KDD Cup 2024

| Aspect | Detail |
|---|---|
| Scale | 4,409 QA pairs + mock web/KG search APIs |
| Domains | 5 domains, 8 question categories |
| Coverage | Popular to long-tail entities, temporal dynamism (years to seconds) |
| Key Finding | Best LLMs <= 34% accuracy; straightforward RAG = 44%; SOTA industry RAG = 63% without hallucination |

**2025 Extension -- CRAG-MM**:
- Multimodal visual QA benchmark
- 5,000 images (3,000 egocentric from Ray-Ban Meta smart glasses)
- 13 domains
- KDD Cup 2025

---

### 2.8 BERGEN (Benchmarking RAG)

**Paper**: Rau et al. (Naver Labs Europe), EMNLP 2024 Findings (arXiv:2407.01102)
**Repo**: https://github.com/naver/bergen

**Core Concept**: Standardized benchmarking library for reproducible RAG experiments.

| Aspect | Detail |
|---|---|
| Retrievers | 20+ supported |
| Rerankers | 4 supported |
| LLMs | 20+ supported |
| Metrics | Match, EM (Exact Match), LLMEval (SOLAR-10.7B judge correlated with GPT-4) |
| Configuration | YAML-based pipeline configuration |

---

### 2.9 GraphRAG-Bench

**Paper**: ICLR 2026
**Repo**: https://github.com/GraphRAG-Bench/GraphRAG-Benchmark

**Focus**: When and why Graph-based RAG outperforms vanilla RAG.

**Task Types**: Fact retrieval, complex reasoning, contextual summarization, creative generation (increasing difficulty).

**Key Finding**: GraphRAG frequently underperforms vanilla RAG on many real-world tasks despite its conceptual promise. The benchmark provides guidelines for when graph-based approaches actually help.

---

### 2.10 Additional Benchmarks

| Benchmark | Focus | Notable Feature |
|---|---|---|
| **RAGEval** (OpenBMB, arXiv:2408.01262, ACL 2025) | Scenario-specific evaluation | Schema-based pipeline generates domain-specific QA from seed docs. Proposes Completeness, Hallucination, Irrelevance metrics |
| **LegalBench-RAG** (2024) | Legal domain RAG | First legal-specific RAG retrieval benchmark |
| **FaithBench** (Vectara, EMNLP 2025) | LLM faithfulness in RAG | Evolving leaderboard for summarization, QA, data-to-text |
| **RAGProbe** (CAIN 2025) | Breaking RAG pipelines | Generates adversarial multi-question prompts; triggers 77% more failures than SOTA |
| **Open RAG Benchmark** (Vectara) | Multimodal PDF understanding | Tests RAG on complex PDFs with tables, charts, images |

---

## 3. Key Evaluation Metrics: Definitions & Formulas

### 3.1 Retrieval Metrics

#### Context Precision @K
**What**: Measures whether relevant chunks are ranked higher than irrelevant ones.

```
Context Precision@K = Σ(k=1..K) [Precision@k × v_k] / (Total relevant items in top K)

Where:
  Precision@k = TP@k / (TP@k + FP@k)
  v_k ∈ {0, 1} = relevance indicator at rank k
```

**ID-Based Variant**: `|retrieved_IDs ∩ reference_IDs| / |retrieved_IDs|`

#### Context Recall
**What**: Whether retrieved context contains all information needed for the ideal answer.

```
Context Recall = (# claims in reference supported by retrieved context) / (# total claims in reference)
```

**Process**: Reference answer is decomposed into claims; each claim is checked for attribution to retrieved context.

**ID-Based Variant**: `|reference_IDs ∩ retrieved_IDs| / |reference_IDs|`

#### Context Entities Recall
**What**: Entity-level coverage in retrieved context vs. reference.

```
Context Entities Recall = |entities(context) ∩ entities(reference)| / |entities(reference)|
```

#### Hit Rate @K / Recall @K
**What**: Whether at least one relevant document appears in top-K results.

```
Hit Rate@K = 1 if any relevant doc in top K, else 0
Recall@K = |relevant docs in top K| / |total relevant docs|
```

#### MRR (Mean Reciprocal Rank)
**What**: Average of reciprocal ranks of the first relevant document.

```
MRR = (1/|Q|) × Σ(i=1..|Q|) 1/rank_i
```

#### nDCG (Normalized Discounted Cumulative Gain)
**What**: Measures ranking quality with graded relevance.

```
DCG@K = Σ(k=1..K) (2^rel_k - 1) / log2(k+1)
nDCG@K = DCG@K / IDCG@K
```

---

### 3.2 Generation Metrics

#### Faithfulness (Groundedness)
**What**: Fraction of response claims supported by retrieved context.

```
Faithfulness = (# claims supported by context) / (# total claims in response)
```

**Process**:
1. Extract individual claims from the generated response
2. For each claim, check via NLI whether it is entailed by the retrieved context
3. Compute the ratio

**Target**: > 0.9 for factual apps; > 0.95 for financial/medical/legal

**Alternative Implementation**: Vectara HHEM-2.1-Open model (trained for hallucination detection)

#### Answer Relevancy (Response Relevancy)
**What**: How relevant the generated answer is to the input query.

```
Answer Relevancy = (1/N) × Σ(i=1..N) cos(E_gi, E_o)

Where:
  E_gi = embedding of reverse-engineered question i (generated from the answer)
  E_o  = embedding of the original question
  N    = number of reverse-engineered questions
```

**Process**: LLM generates N hypothetical questions that the answer would address. Mean cosine similarity between those and the actual question gives the score.

#### Hallucination Rate
**What**: Fraction of claims in the response NOT supported by context.

```
Hallucination Rate = 1 - Faithfulness
                   = (# unsupported claims) / (# total claims)
```

**Detection Methods**:
- **Entailment-based (NLI)**: Use NLI model to check if context entails answer
- **Self-consistency**: Sample multiple responses and check agreement
- **LLM-as-judge**: Prompt LLM to identify unsupported claims
- **Learned models**: HHEM, TLM, finetuned classifiers

#### Factual Correctness
**What**: Whether claims in the response match the ground truth answer.

```
Factual Correctness = F1(claims(response), claims(ground_truth))

Where:
  TP = claims in both response and ground truth
  FP = claims in response but not in ground truth
  FN = claims in ground truth but not in response
```

---

### 3.3 Robustness Metrics (from RGB)

| Metric | Formula | Measures |
|---|---|---|
| Noise Robustness | `1 - (Misleading Rate)` | Ability to ignore irrelevant context |
| Negative Rejection | Rejection Rate when context is insufficient | Knowing when NOT to answer |
| Information Integration | Accuracy on multi-passage questions | Synthesizing across documents |
| Counterfactual Robustness | Error Detection Rate in counterfactual context | Identifying incorrect information |

---

### 3.4 End-to-End Metrics

#### Answer Correctness (RAGAS)
```
Answer Correctness = w1 × Factual Similarity + w2 × Semantic Similarity

Where:
  Factual Similarity = F1(claims(response), claims(ground_truth))
  Semantic Similarity = cosine(embed(response), embed(ground_truth))
  w1 + w2 = 1 (default: w1=0.75, w2=0.25)
```

#### Exact Match (EM)
```
EM = 1 if normalize(response) == normalize(ground_truth), else 0
```

#### F1 Score (Token-level)
```
F1 = 2 × (Token Precision × Token Recall) / (Token Precision + Token Recall)
```

---

## 4. Recent Papers on RAG Evaluation (2024-2026)

### 4.1 Surveys

| Paper | Year | Key Contribution |
|---|---|---|
| **"Evaluation of Retrieval-Augmented Generation: A Survey"** (Yu et al., arXiv:2405.07437) | 2024 | Proposes Auepora framework; unifies RAG evaluation process; surveys benchmarks and metrics |
| **"Retrieval Augmented Generation Evaluation in the Era of LLMs"** (Gan et al., arXiv:2504.14891) | Apr 2025 | Most comprehensive recent survey; covers traditional and LLM-based evaluation methods |
| **Awesome-RAG-Evaluation** (GitHub: YHPeter/Awesome-RAG-Evaluation) | Ongoing | Living repository tracking all RAG evaluation papers |

### 4.2 New Evaluation Frameworks & Methods

| Paper | Year | Venue | Key Idea |
|---|---|---|---|
| **RAGChecker** (Amazon, arXiv:2408.08067) | 2024 | NeurIPS 2024 | Claim-level entailment; significantly better correlation with human judgments than RAGAS/BERTScore |
| **ARES** (Stanford, arXiv:2311.09476) | 2023/24 | -- | Finetuned DeBERTa judges + PPI calibration; cheap and domain-robust |
| **RAGEval** (OpenBMB, arXiv:2408.01262) | 2024 | ACL 2025 | Schema-based domain-specific test generation; Completeness/Hallucination/Irrelevance metrics |
| **RAGProbe** (arXiv, CAIN 2025) | 2025 | CAIN 2025 | Adversarial scenario generation for CI/CD; triggers 77% more failures than existing methods |
| **VERA** (Ding et al.) | Aug 2024 | -- | Validation and Evaluation of Retrieval-Augmented Systems |
| **FaithJudge** (Vectara, arXiv:2505.04847) | 2025 | EMNLP 2025 | LLM-as-judge with diverse human-annotated hallucination examples; outperforms HHEM on FaithBench |
| **Open RAG Eval** (Vectara + U. Waterloo) | Apr 2025 | -- | Reference-free eval using UMBRELA + HHEM; no golden answers needed |
| **RARE** (arXiv:2506.00789) | 2025 | -- | Retrieval-Aware Robustness Evaluation |

### 4.3 Emerging Trends

**1. Claim-Level Granularity Over Response-Level**
- RAGChecker and RAGAS both moved from response-level to claim-level evaluation
- Decompose answers into atomic claims, verify each independently
- Better diagnostic power: identifies specific failure modes

**2. Finetuned Small Models vs. LLM-as-Judge**
- ARES: DeBERTa-v3-large (437M) outperforms GPT-3.5 as judge
- RAGBench/TRACe: Finetuned RoBERTa outperforms LLM-based evaluation
- Cleanlab TLM: Wrapper approach using uncertainty quantification
- Trade-off: small models are cheaper but less generalizable; LLMs are expensive but flexible

**3. Reference-Free Evaluation**
- RAGAS pioneered this (2023); Open RAG Eval (2025) extends it
- UMBRELA scoring: No golden chunks or golden answers needed
- Critical for production monitoring where ground truth is unavailable

**4. Adversarial/Stress Testing**
- RAGProbe: Generates multi-question prompts that trigger up to 91% failure rates
- RGB: Tests noise robustness, negative rejection, counterfactual robustness
- Giskard RAGET: Adversarial queries for security and business failure detection

**5. Production-Oriented Evaluation**
- Arize Phoenix: OpenTelemetry-based observability + evaluation
- LangSmith: Online evaluation on production traffic
- TruLens: OpenTelemetry support + agent evaluation
- Trend: CI/CD integration, automated quality gates, production-to-test conversion

**6. Multimodal RAG Evaluation**
- RAGAS v0.2: Multimodal Faithfulness and Multimodal Relevance metrics
- CRAG-MM (Meta, 2025): Visual QA benchmark with egocentric images
- Open RAG Benchmark (Vectara): PDFs with tables, charts, images

**7. Agent/Agentic RAG Evaluation**
- DeepEval: Task Completion, Tool Correctness metrics
- RAGAS: Agent Goal Accuracy, Tool Call Accuracy, Topic Adherence
- TruLens: Goal-Plan-Action alignment framework (95% coverage of agent errors on TRAIL dataset)

**8. Evolving Leaderboards**
- Vectara Hallucination Leaderboard (since 2023): Tracks hallucination rates across LLMs
- FaithBench (EMNLP 2025): Evolving leaderboard for RAG faithfulness
- Chatbot Arena: Community-driven LLM comparison (not RAG-specific but influential)

---

## 5. Framework Comparison Matrix

| Framework | Type | Reference-Free | LLM-as-Judge | Finetuned Judge | Production Monitoring | Agent Support | Open Source |
|---|---|---|---|---|---|---|---|
| RAGAS | Metrics library | Yes | Yes | No | No | Yes | Yes |
| DeepEval | Testing framework | Partial | Yes | No | Via Confident AI | Yes | Yes |
| ARES | Evaluation system | No (needs PPI) | No | Yes (DeBERTa) | No | No | Yes |
| TruLens | Observability + eval | Yes | Yes | No | Yes (OTel) | Yes | Yes |
| RAGChecker | Diagnostic framework | No | Yes | No | No | No | Yes |
| Giskard | Testing platform | Yes | Yes | No | No | No | Yes |
| UpTrain | Observability + eval | Yes | Yes | No | Yes | No | Yes |
| Cleanlab TLM | Trustworthiness scorer | Yes | Yes | No | Yes | No | Partial |
| Open RAG Eval | Evaluation framework | Yes | Yes | Yes (HHEM) | No | No | Yes |
| Arize Phoenix | Observability platform | Yes | Yes | No | Yes (OTel) | Yes | Yes |
| LangSmith | Observability platform | Partial | Yes | No | Yes | Yes | No |

---

## 6. Recommended Evaluation Strategy for Production RAG

### Development Phase
1. **Synthetic test generation**: RAGAS or RAGEval to auto-generate test datasets
2. **Comprehensive metrics**: RAGChecker for fine-grained claim-level diagnostics
3. **Stress testing**: RAGProbe for adversarial scenarios; RGB-style robustness tests
4. **Security testing**: Giskard RAGET for prompt injection, bias detection

### CI/CD Phase
1. **Unit tests**: DeepEval (pytest-like) with quality thresholds
2. **Regression detection**: RAGProbe integration for automated failure detection
3. **Benchmark tracking**: RAGAS metrics as quality gates

### Production Phase
1. **Real-time monitoring**: Arize Phoenix or TruLens with OpenTelemetry
2. **Hallucination detection**: Cleanlab TLM or Vectara HHEM for per-response scoring
3. **Reference-free evaluation**: Open RAG Eval for continuous assessment without golden answers
4. **Feedback loops**: Convert production failures into evaluation datasets

---

## Sources

### Frameworks
- [RAGAS Documentation](https://docs.ragas.io/en/stable/)
- [RAGAS Paper (arXiv:2309.15217)](https://arxiv.org/abs/2309.15217)
- [DeepEval RAG Evaluation Guide](https://deepeval.com/guides/guides-rag-evaluation)
- [DeepEval GitHub](https://github.com/confident-ai/deepeval)
- [ARES Paper (arXiv:2311.09476)](https://arxiv.org/abs/2311.09476)
- [ARES GitHub](https://github.com/stanford-futuredata/ARES)
- [TruLens RAG Triad](https://www.trulens.org/getting_started/core_concepts/rag_triad/)
- [TruLens GitHub](https://github.com/truera/trulens)
- [RAGChecker Paper (arXiv:2408.08067)](https://arxiv.org/abs/2408.08067)
- [RAGChecker GitHub](https://github.com/amazon-science/RAGChecker)
- [Giskard RAGET Documentation](https://docs.giskard.ai/oss/sdk/business.html)
- [UpTrain on Haystack](https://haystack.deepset.ai/cookbook/rag_eval_uptrain)
- [Cleanlab TLM Benchmarking](https://cleanlab.ai/blog/rag-tlm-hallucination-benchmarking/)
- [Open RAG Eval (Vectara)](https://github.com/vectara/open-rag-eval)
- [Arize Phoenix GitHub](https://github.com/Arize-ai/phoenix)
- [Snowflake Benchmarking RAG Triad](https://www.snowflake.com/en/engineering-blog/benchmarking-LLM-as-a-judge-RAG-triad-metrics/)

### Benchmarks
- [BEIR Benchmark](https://github.com/beir-cellar/beir)
- [CRAG (Meta) Paper (arXiv:2406.04744)](https://arxiv.org/abs/2406.04744)
- [CRAG GitHub](https://github.com/facebookresearch/CRAG)
- [CRAG-MM (KDD Cup 2025)](https://kddcup25.github.io/)
- [RGB Paper (arXiv:2309.01431)](https://arxiv.org/abs/2309.01431)
- [CRUD-RAG (ACM TOIS)](https://dl.acm.org/doi/10.1145/3701228)
- [RAGBench Paper (arXiv:2407.11005)](https://arxiv.org/abs/2407.11005)
- [MultiHop-RAG (OpenReview)](https://openreview.net/forum?id=t4eB3zYWBK)
- [BERGEN (Naver, arXiv:2407.01102)](https://arxiv.org/abs/2407.01102)
- [GraphRAG-Bench (ICLR 2026)](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)
- [RAGEval Paper (arXiv:2408.01262)](https://arxiv.org/abs/2408.01262)
- [RAGProbe (CAIN 2025)](https://conf.researchr.org/details/cain-2025/cain-2025-call-for-papers/13/RAGProbe-Breaking-RAG-Pipelines-with-Evaluation-Scenarios)

### Surveys & Recent Papers
- [Evaluation of RAG: A Survey (arXiv:2405.07437)](https://arxiv.org/abs/2405.07437)
- [RAG Evaluation in the Era of LLMs (arXiv:2504.14891)](https://arxiv.org/html/2504.14891v1)
- [FaithJudge (arXiv:2505.04847)](https://arxiv.org/abs/2505.04847)
- [Awesome-RAG-Evaluation Repository](https://github.com/YHPeter/Awesome-RAG-Evaluation)
- [Evidently AI: 7 RAG Benchmarks](https://www.evidentlyai.com/blog/rag-benchmarks)
- [Confident AI: RAG Evaluation Metrics](https://www.confident-ai.com/blog/rag-evaluation-metrics-answer-relevancy-faithfulness-and-more)
- [Best RAG Evaluation Tools 2026 (Maxim)](https://www.getmaxim.ai/articles/the-5-best-rag-evaluation-tools-you-should-know-in-2026/)
- [RAG Evaluation: Metrics, Frameworks & Testing 2026 (Prem AI)](https://blog.premai.io/rag-evaluation-metrics-frameworks-testing-2026/)
