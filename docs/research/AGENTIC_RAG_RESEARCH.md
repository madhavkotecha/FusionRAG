# Agentic RAG: State-of-the-Art Research Survey (2025-2026)

> Comprehensive survey of 40+ papers from the last 12 months, with framework analysis and mapping to our pipeline component system.

---

## Table of Contents

1. [Key Trends](#1-key-trends)
2. [Agentic RAG Architectures](#2-agentic-rag-architectures)
3. [Multi-Hop Reasoning](#3-multi-hop-reasoning)
4. [Graph-Based RAG](#4-graph-based-rag)
5. [Query Decomposition & Planning](#5-query-decomposition--planning)
6. [Reranking Innovations](#6-reranking-innovations)
7. [RAG Evaluation](#7-rag-evaluation)
8. [Streaming & Latency-Aware RAG](#8-streaming--latency-aware-rag)
9. [Multimodal RAG](#9-multimodal-rag)
10. [RL-Based RAG Training](#10-rl-based-rag-training)
11. [Hybrid & Adaptive Approaches](#11-hybrid--adaptive-approaches)
12. [Structured Data RAG](#12-structured-data-rag)
13. [Existing Framework Analysis](#13-existing-framework-analysis)
14. [Component Registry Gap Analysis](#14-component-registry-gap-analysis)
15. [New Components Added](#15-new-components-added)

---

## 1. Key Trends

Six paradigm shifts identified across the surveyed literature:

| Trend | From | To | Key Papers |
|-------|------|----|------------|
| **Pipeline to Policy** | Fixed retrieve-then-read | RL-trained retrieval policies | ReSearch, RAG-RL, MMOA-RAG |
| **Test-Time Compute Scaling** | Fixed inference budget | Adaptive compute allocation | Search-o1, MCTS-RAG, CoRAG |
| **Graph as Universal Index** | Flat vector stores | KG + vector hybrid indexes | LightRAG, HippoRAG 2, GFM-RAG |
| **Retrieval Inside Reasoning** | Pre-reasoning retrieval | Interleaved retrieval + CoT | DeepRAG, IRCoT, AirRAG |
| **Latency as First-Class** | Accuracy-only optimization | Accuracy + latency co-optimization | Speculative RAG, RAPID, StreamingRAG |
| **MCP/Tool Integration** | Monolithic pipelines | Tool-calling + protocol-based composition | RAG-MCP, UltraRAG, A-RAG |

---

## 2. Agentic RAG Architectures

### 2.1 Surveys & Foundations

| Paper | Date | Key Contribution |
|-------|------|------------------|
| **Agentic RAG Survey** (arXiv:2501.09136) | Jan 2025 | Taxonomy: Single-Agent, Multi-Agent, Hierarchical Agentic RAG |
| **A-RAG** (arXiv:2502.XXXXX) | Feb 2026 | Autonomous RAG with multi-agent negotiation and cooperative decision-making |
| **PRISM** | 2025 | Policy-based retrieval integration with structured memory |

### 2.2 Architecture Patterns

**Single-Agent Agentic RAG** (Simplest)
```
Query -> Router -> [Retrieve | Web Search | Direct Answer] -> Generate -> Reflect -> Output
```
- Components: Query Router, Retriever, Generator, Reflection Agent
- Use when: Single-domain, moderate complexity queries
- Our coverage: Query Router, Reflection Agent, LLM Generator

**Multi-Agent Agentic RAG** (Collaborative)
```
Query -> Planner -> [Retriever Agent, Analyzer Agent, Critic Agent] -> Synthesizer -> Output
```
- Components: Planner, multiple specialized agents, Orchestrator
- Use when: Multi-domain queries, complex reasoning
- Our coverage: Orchestrator Agent, CoRAG Planner, Tool Use Agent

**Hierarchical Agentic RAG** (Enterprise)
```
Query -> Meta-Agent -> [Domain Router -> [Sub-Agent Pool]] -> Aggregator -> QA Agent -> Output
```
- Components: Meta-planner, domain routers, sub-agent pools, aggregator
- Use when: Enterprise multi-tenant, many data sources
- **Gap**: No meta-agent or hierarchical routing in our registry

### 2.3 Self-Cognition Gate (KAG)

KAG introduces a **self-cognition gate** that checks whether the LLM already knows the answer before retrieving:
- If confidence > threshold: answer directly (no retrieval cost)
- If confidence < threshold: plan and retrieve
- **Impact**: 30-40% queries avoid retrieval entirely
- **Gap**: Not in our registry. Added as `self_cognition_gate` component.

---

## 3. Multi-Hop Reasoning

### 3.1 Core Papers

| Paper | arXiv | Approach | Improvement |
|-------|-------|----------|-------------|
| **CoRAG** | 2501.14342 | Chain-of-Retrieval with rejection sampling | NeurIPS 2025, SOTA on multi-hop |
| **HopRAG** | 2025 | Graph-augmented passage linking for hop reasoning | +15% on HotpotQA |
| **DeepRAG** | 2025 | Retrieval-augmented reasoning with atomic decisions | Retrieval within CoT steps |
| **MCTS-RAG** | 2503.20757 | Monte Carlo Tree Search over retrieval paths | +20% on complex queries |
| **AirRAG** | 2025 | Activated Implicit Retrieval-augmented Reasoning | Interleaved retrieval + generation |
| **Stop-RAG** | 2025 | Adaptive stopping criteria for retrieval depth | 40% fewer retrievals, same quality |

### 3.2 CoRAG Deep Dive

CoRAG (Chain-of-Retrieval Augmented Generation) is the most impactful multi-hop paper:

1. **Training**: Uses rejection sampling to create (query, retrieval_chain, answer) triples
2. **Inference strategies**:
   - Greedy: one sub-query at a time
   - Best-of-N: sample N chains, pick highest-scoring
   - Beam search: maintain top-K partial chains
   - **Tree search**: MCTS over retrieval paths (best quality)
3. **Key insight**: Train the LLM to generate sub-queries, not just answers

**Our CoRAG Planner already covers this.** Consider adding tree_search as default strategy.

### 3.3 DeepRAG Pattern

DeepRAG introduces **retrieval as an atomic reasoning step**:
```
Think Step 1 -> [Need Info? Yes] -> Retrieve -> Think Step 2 -> [Need Info? No] -> Continue -> Answer
```
- Each CoT step can trigger retrieval
- Binary decision: retrieve or continue reasoning
- Trained with RL to optimize when to retrieve
- **Gap**: No interleaved retrieval-reasoning component. Added as `deep_rag_agent`.

### 3.4 Stop-RAG: Adaptive Retrieval Depth

Stop-RAG learns **when to stop retrieving**:
- Calibrated confidence estimator on retrieved context
- If accumulated evidence is sufficient: stop and generate
- **Impact**: 40% fewer retrieval calls with same answer quality
- **Gap**: No adaptive stopping component. Added as `adaptive_retrieval_controller`.

---

## 4. Graph-Based RAG

### 4.1 Papers

| Paper | Key Innovation |
|-------|---------------|
| **LightRAG** | Dual-level (local/global) keyword retrieval over KG |
| **GraphRAG** (Microsoft) | Community detection + hierarchical summaries |
| **EcphoryRAG** | Brain-inspired memory cue activation over KG |
| **HippoRAG 2** | Hippocampal-inspired entity indexing with pattern separation |
| **GFM-RAG** | Graph Foundation Model for reasoning over heterogeneous graphs |
| **DEG-RAG** | Dynamic Entity Graph with real-time updates |
| **Practical GraphRAG** | Cost-reduction techniques for production GraphRAG |

### 4.2 LightRAG Dual-Retrieval Pattern

LightRAG's novel approach combines:
1. **Local retrieval**: Match query keywords to entity names, retrieve entity descriptions + linked chunks
2. **Global retrieval**: Match query keywords to relation keywords, retrieve relation descriptions + community summaries
3. **Hybrid mode**: Combine both with deduplication
4. **Mix mode**: Add vector similarity as third signal

**Our graph_retriever partially covers this.** Consider adding `lightrag_dual_retriever` with explicit local/global modes.

### 4.3 HippoRAG 2: Brain-Inspired Retrieval

HippoRAG 2 models the hippocampus:
- **Parahippocampal Cortex**: Entity extraction and encoding
- **Entorhinal Cortex**: Entity-to-passage linking via KG edges
- **Pattern Separation**: Distinguish similar but different entities
- **Pattern Completion**: From partial query, reconstruct full retrieval context

**Gap**: No brain-inspired retrieval model. The concepts map to our graph_retriever + entity resolution.

### 4.4 GFM-RAG: Graph Foundation Model

- Pre-trained graph neural network that learns entity/relation representations
- At query time: encode query as graph, match against corpus graph
- **Key advantage**: Generalizes across domains without fine-tuning
- **Gap**: No GFM-based retriever. Added as `gfm_retriever` component.

---

## 5. Query Decomposition & Planning

### 5.1 Papers

| Paper | Approach |
|-------|----------|
| **Collab-RAG** | Collaborative decomposition with multiple LLM agents |
| **PAR-RAG** | Plan-and-Refine: iterative decomposition with context accumulation |
| **ComposeRAG** | Compositional sub-query routing to different retrieval strategies |
| **Search-o1** | Chain-of-search with agentic reasoning |
| **HiPRAG** | Hierarchical Prompt RAG with progressive detail levels |
| **Progressive Searching RAG** | Coarse-to-fine search with progressive refinement |

### 5.2 Search-o1 Pattern

Search-o1 introduces **Reason-in-Documents** within extended thinking:
1. Generate extended thinking (chain-of-thought)
2. At each reasoning step, decide: search or continue
3. If search: generate search query, retrieve, inject into reasoning
4. Continue reasoning with retrieved information
5. Final answer after reasoning converges

**Impact**: Combines o1-style reasoning with agentic retrieval
**Gap**: No "reason-in-documents" agent. Our DeepRAG agent covers this pattern.

### 5.3 ComposeRAG: Compositional Routing

ComposeRAG routes sub-queries to different retrieval strategies:
```
"What is NVIDIA's revenue and how does it compare to AMD?" ->
  Sub-Q1: "NVIDIA revenue 2025" -> [Table retriever]
  Sub-Q2: "AMD revenue 2025" -> [Table retriever]
  Sub-Q3: "Compare NVIDIA vs AMD" -> [Text retriever]
  -> Compose answers
```
- Each sub-query matched to optimal retriever type
- **Our query_router + subquery_decomposer partially covers this.**

### 5.4 KAG Planner: Logic Form DSL

KAG's planner decomposes queries into a **Logic Form** operator DAG:
```
Query: "What awards did films directed by February 2026 Oscar nominees win?"
Plan:
  Step 1: kg_retrieval("February 2026 Oscar nominees") -> nominees
  Step 2: kg_retrieval("films directed by {nominees}") -> films
  Step 3: text_retrieval("awards won by {films}") -> awards
  Step 4: deduce(nominees, films, awards) -> answer
```

Operators: `kg_retrieval`, `text_retrieval`, `math`, `deduce`, `sort`, `compare`

**Our kag_planner covers this pattern.**

---

## 6. Reranking Innovations

### 6.1 Papers

| Paper | Innovation |
|-------|-----------|
| **Reranking Survey** (arXiv:2509.25085) | Comprehensive taxonomy of reranking approaches |
| **RankLLM/RankZephyr** | Distilled LLM rerankers with sliding window |
| **Listwise vs Pointwise** | Listwise reranking outperforms pointwise by 3-5% |
| **Context Compression** | Compress retrieved context before generation |

### 6.2 Context Compression (New Pattern)

**CompactRAG** and **LinearRAG** introduce context compression:
- After retrieval, compress documents to keep only query-relevant information
- Reduces token count by 50-70% with <2% quality loss
- Methods: extractive (sentence selection), abstractive (summarization), token pruning

**Gap**: No context compression component. Added as `context_compressor`.

### 6.3 Relevance Filtering with NLI

Use NLI (Natural Language Inference) models to filter retrieved documents:
- Classify each document as: entailment (relevant), contradiction (irrelevant), neutral
- Remove contradicting documents before generation
- **Impact**: Reduces hallucination from conflicting context
- **Gap**: Added as option in adaptive_retrieval_controller.

---

## 7. RAG Evaluation

### 7.1 Papers

| Paper | Focus |
|-------|-------|
| **RAGAS v2** | Component-level evaluation metrics |
| **FaithJudge** | Faithfulness evaluation without reference answers |
| **RAGLens** | Diagnostic tool for identifying RAG failure modes |
| **GraphRAG-Bench** | Benchmarks for graph-based RAG |
| **RAGEval** | Automated evaluation dataset generation |
| **SafeRAG** | Safety evaluation for adversarial RAG attacks |
| **AgenticRAGTracer** | Tracing and observability for agentic RAG |

### 7.2 Key Metrics

| Metric | What It Measures | Range |
|--------|-----------------|-------|
| **Context Precision** | Retrieved docs relevance | 0-1 |
| **Context Recall** | Coverage of gold context | 0-1 |
| **Faithfulness** | Answer grounded in context | 0-1 |
| **Answer Relevance** | Answer addresses query | 0-1 |
| **Noise Robustness** | Performance with irrelevant context | 0-1 |
| **Counterfactual Robustness** | Resistance to misleading context | 0-1 |

### 7.3 AgenticRAGTracer

Observability tool providing:
- Per-hop retrieval quality traces
- Token usage attribution per component
- Latency breakdown across pipeline
- Failure mode classification

**Gap**: No built-in evaluation/tracing component. Added as `rag_evaluator`.

---

## 8. Streaming & Latency-Aware RAG

### 8.1 Papers

| Paper | Innovation |
|-------|-----------|
| **Speculative RAG** | Draft with small model, verify with large model |
| **RAPID** | Parallel retrieval and generation |
| **StreamingRAG** | Progressive context injection during generation |
| **Dynamic Streaming** | Adaptive chunk selection during stream |
| **RT-RAG** | Real-time RAG with deadline-aware scheduling |

### 8.2 Speculative RAG Pattern

```
                    ┌─ Small Model: Draft Answer 1 (Subset A) ─┐
Query + Retrieved → ├─ Small Model: Draft Answer 2 (Subset B) ─┼→ Large Model: Verify Best → Output
                    └─ Small Model: Draft Answer 3 (Subset C) ─┘
```

- Parallel drafting with small model on different context subsets
- Single verification pass with large model
- **Impact**: 2-3x faster, maintains quality
- **Gap**: No speculative RAG component. Added as `speculative_generator`.

### 8.3 RAPID: Parallel Retrieval + Generation

Start generating while still retrieving:
1. Fire retrieval query
2. Start generating with available context (even partial)
3. As more documents arrive, inject into generation stream
4. **Impact**: 50% latency reduction on long retrieval chains

**Gap**: Requires streaming architecture support. Added as `streaming_retriever`.

---

## 9. Multimodal RAG

### 9.1 Papers

| Paper | Focus |
|-------|-------|
| **Multimodal RAG Survey** | Comprehensive taxonomy |
| **VisRAG** | Vision-language model for document understanding |
| **Multimodal KG RAG** | Knowledge graphs with image/video entities |
| **ColPali** | Late interaction for visual document retrieval |

### 9.2 VisRAG Pattern

Instead of OCR + text extraction:
1. Embed document pages as images using vision encoder
2. Retrieve by visual similarity
3. Generate using vision-language model with page images as context

**Impact**: Handles charts, diagrams, complex layouts that text extraction misses

**Gap**: No multimodal components in registry. Added `multimodal_embedder` and `vision_generator`.

---

## 10. RL-Based RAG Training

### 10.1 Papers

| Paper | Approach |
|-------|----------|
| **ReSearch** | RL for learning when and what to retrieve |
| **RAG-RL** | Reward model for retrieval policy optimization |
| **MMOA-RAG** | Multi-objective optimization (accuracy + cost + latency) |
| **Search-R2** | Reinforcement learning for search refinement |
| **ARR** | Aligned Retriever-Reader with RL |

### 10.2 MMOA-RAG: Multi-Objective Optimization

Optimizes three objectives simultaneously:
1. **Accuracy**: Answer correctness
2. **Cost**: Token usage (retrieval + generation)
3. **Latency**: End-to-end response time

Uses Pareto frontier to find optimal operating points.

**Gap**: No cost/latency-aware optimization. This is an architectural concern for the orchestrator.

### 10.3 RAG-RL Training Pipeline

```
1. Collect trajectories: (query, retrieval_actions, answer, reward)
2. Train policy: which documents to retrieve, when to stop
3. Train reward model: estimate answer quality from context
4. Fine-tune retrieval policy with PPO/DPO
```

**Gap**: Training infrastructure is out of scope for pipeline components, but the trained policies manifest as component configs.

---

## 11. Hybrid & Adaptive Approaches

### 11.1 Papers

| Paper | Innovation |
|-------|-----------|
| **RouteRAG** | Dynamic routing between retrieval strategies |
| **ACC-RAG** | Adaptive Context Compression RAG |
| **Zero-RAG** | RAG with zero training data |
| **Neurosymbolic RAG** | Combining neural retrieval with symbolic reasoning |

### 11.2 RouteRAG Pattern

Dynamic routing based on query characteristics:
```
Query Analysis:
  - Complexity: simple/moderate/complex
  - Type: factual/analytical/creative
  - Domain: in-domain/out-of-domain

Routing Table:
  simple + factual + in-domain → Direct dense retrieval
  moderate + analytical + in-domain → Hybrid + reranker
  complex + analytical + any → Multi-hop + graph
  any + any + out-of-domain → Web search + verification
```

**Our query_router covers this.** Consider adding query complexity estimation.

### 11.3 Corpus Scaling Laws

Recent research on how RAG performance scales with corpus size:
- Retrieval quality follows **log-linear scaling** with corpus size
- Adding more documents has diminishing returns after ~1M
- **Selective indexing** (index quality > quantity) outperforms brute-force
- **Implication**: Our indexer components should support quality-based filtering

---

## 12. Structured Data RAG

### 12.1 Papers

| Paper | Focus |
|-------|-------|
| **TableRAG** | RAG over tabular data with schema understanding |
| **TabRAG** | Table-aware retrieval and generation |

### 12.2 TableRAG Pattern

1. **Schema retrieval**: Match query to table schemas
2. **Cell retrieval**: Find relevant cells using column-aware encoding
3. **SQL generation**: Generate SQL from query + schema + sample cells
4. **Execution**: Run SQL on database
5. **Generation**: Produce natural language answer from SQL results

**Gap**: No table/SQL retrieval components. Added `table_retriever`.

---

## 13. Existing Framework Analysis

### 13.1 LightRAG

**Architecture**: Graph-augmented dual-keyword retrieval
- **Novel**: Local/global/hybrid/mix retrieval modes
- **Entity extraction**: LLM with gleaning (multiple passes)
- **Entity resolution**: Embedding-based deduplication
- **Indexing**: Nano-VectorDB + NetworkX graph
- **Community summaries**: Map-reduce per community
- **Key pattern**: Dual-level keywords (entity names + relation keywords)

### 13.2 KAG (Knowledge-Augmented Generation)

**Architecture**: Most sophisticated - agentic planning over SPG
- **Novel**: Logic Form DSL for query decomposition
- **Planners**: Static DAG planner + iterative replanner
- **Retrieval**: Priority groups (KG first, then text, then web)
- **Self-cognition gate**: Skip retrieval if LLM already knows
- **Deduce operations**: Logical reasoning over retrieved facts
- **MCP integration**: External tool calling via MCP protocol
- **Key pattern**: Operator DAG with typed data flow

### 13.3 CoRAG

**Architecture**: Monte Carlo tree search over retrieval paths
- **Novel**: Tree search at inference, rejection sampling at training
- **Sub-query generation**: Iterative, context-aware decomposition
- **Scoring**: Log-probability of correct answer given retrieval chain
- **Strategies**: Greedy, Best-of-N, Beam, Tree Search
- **Key pattern**: Retrieval as a sequential decision process

### 13.4 UltraRAG

**Architecture**: MCP-native declarative pipeline composition
- **Novel**: YAML DSL with loop/branch primitives
- **Pipelines**: IRCoT, Search-R1, Search-o1, IterRetGen, WebNote
- **MCP server**: Each pipeline exposes tools via MCP
- **Knowledge base management**: Multi-index with routing
- **Key pattern**: Declarative pipeline composition with control flow

---

## 14. Component Registry Gap Analysis

### Currently Well-Covered
- Chunkers (7 types including proposition, contextual, hierarchical)
- Embedders (8 providers including BGE-M3 multi-modal)
- Extractors (4 types including CoRAG subquery decomposer)
- Graph builders (2 types)
- Indexers (2 types)
- Retrievers (4 types including graph and web)
- Rerankers (4 types including LLM listwise)
- Generator (1 comprehensive LLM generator)
- Storage (3 backends)
- Agents (4 types including reflection and memory)
- Planners (3 types including MCTS and KAG)

### Identified Gaps (from research)

| Gap | Research Source | Priority | Status |
|-----|---------------|----------|--------|
| Self-cognition gate | KAG | HIGH | **Added** |
| Deep RAG agent (interleaved retrieval+reasoning) | DeepRAG, AirRAG | HIGH | **Added** |
| Adaptive retrieval controller (stop criteria) | Stop-RAG | HIGH | **Added** |
| Context compressor | CompactRAG, LinearRAG | HIGH | **Added** |
| Speculative generator | Speculative RAG | MEDIUM | **Added** |
| RAG evaluator | RAGAS, FaithJudge | MEDIUM | **Added** |
| Streaming retriever | RAPID, StreamingRAG | MEDIUM | **Added** |
| Table retriever | TableRAG | MEDIUM | **Added** |
| GFM retriever | GFM-RAG | LOW | **Added** |
| Multimodal embedder | VisRAG, ColPali | LOW | **Added** |
| Vision generator | VisRAG | LOW | **Added** |
| LightRAG dual retriever | LightRAG | LOW | Covered by graph_retriever config |
| Meta-agent / hierarchical routing | Agentic RAG Survey | LOW | Covered by orchestrator + router |
| RL-trained retrieval policy | RAG-RL, MMOA-RAG | LOW | Training infra, not component |

---

## 15. New Components Added

The following 11 components were added to the component registry based on this research:

### Agents
1. **Self-Cognition Gate** - KAG-inspired confidence check before retrieval
2. **Deep RAG Agent** - Interleaved retrieval within chain-of-thought reasoning
3. **Adaptive Retrieval Controller** - Stop-RAG-inspired dynamic retrieval depth

### Retrievers
4. **Streaming Retriever** - RAPID-style progressive context injection
5. **Table Retriever** - TableRAG-style structured data retrieval
6. **GFM Retriever** - Graph Foundation Model for cross-domain retrieval

### Rerankers
7. **Context Compressor** - Post-retrieval context compression and filtering

### Generators
8. **Speculative Generator** - Draft-verify pattern with small+large models
9. **Vision Generator** - Multimodal generation from document images

### Embedders
10. **Multimodal Embedder** - Vision-language document embedding (ColPali/VisRAG)

### Evaluation
11. **RAG Evaluator** - Built-in RAGAS-style evaluation and tracing

---

## References

### Agentic RAG
- Agentic RAG Survey, arXiv:2501.09136, Jan 2025
- A-RAG: Autonomous RAG with Multi-Agent Negotiation, Feb 2026

### Multi-Hop Reasoning
- CoRAG: Chain-of-Retrieval Augmented Generation, arXiv:2501.14342, NeurIPS 2025
- MCTS-RAG: Monte Carlo Tree Search for RAG, arXiv:2503.20757
- DeepRAG: Retrieval-Augmented Reasoning with Atomic Decisions, 2025
- AirRAG: Activated Implicit Retrieval-augmented Reasoning, 2025
- Stop-RAG: Adaptive Stopping for Retrieval, 2025
- HopRAG: Graph-augmented Multi-hop Retrieval, 2025

### Graph RAG
- LightRAG: Simple and Fast Retrieval-Augmented Generation, 2024-2025
- GraphRAG: Graph-based RAG for Global Questions, Microsoft, 2024
- HippoRAG 2: Brain-inspired Long-term Memory for LLMs, 2025
- GFM-RAG: Graph Foundation Model for RAG, 2025-2026
- DEG-RAG: Dynamic Entity Graph RAG, 2025
- EcphoryRAG: Brain-inspired Memory Cue Activation, 2025

### Query Decomposition
- Search-o1: Agentic Search within Extended Thinking, 2025
- ComposeRAG: Compositional Sub-query Routing, 2025
- PAR-RAG: Plan-and-Refine Retrieval, 2025
- HiPRAG: Hierarchical Prompt RAG, 2025-2026

### Reranking & Compression
- Reranking Survey, arXiv:2509.25085, 2025
- CompactRAG: Context Compression for RAG, 2025-2026
- LinearRAG: Linear Complexity Context Processing, 2025

### Evaluation
- RAGAS v2: Component-level RAG Evaluation, 2025
- FaithJudge: Faithfulness without Reference, 2025
- AgenticRAGTracer: Observability for Agentic RAG, 2025

### Streaming & Latency
- Speculative RAG: Draft-Verify for Fast Generation, 2025
- RAPID: Parallel Retrieval and Generation, 2025
- RT-RAG: Real-time RAG with Deadline Scheduling, 2025

### RL-Based
- ReSearch: RL for Retrieval Policies, 2025
- MMOA-RAG: Multi-Objective Optimization, 2025
- Search-R2: RL for Search Refinement, 2025-2026

### Multimodal
- VisRAG: Vision-Language RAG, 2025
- ColPali: Late Interaction Visual Retrieval, 2024-2025

### Structured Data
- TableRAG: RAG over Tabular Data, 2025

### Frameworks Analyzed
- LightRAG: https://github.com/HKUDS/LightRAG
- KAG: https://github.com/OpenSPG/KAG
- CoRAG: https://github.com/princeton-nlp/CoRAG
- UltraRAG: https://github.com/UltraRAG/UltraRAG
