# Mixture of Retrieval Experts (MoRE) Architecture Research

> Deep research survey on adaptive and dynamic RAG routing architectures (2024-2026), informing the design of a production "Mixture of Retrieval Experts" system.

**Date**: March 2026
**Scope**: 25+ papers across adaptive routing, self-reflective RAG, corrective retrieval, speculative execution, RL-based policies, modular frameworks, and ensemble/MoE retrieval.

---

## Table of Contents

1. [Adaptive-RAG: Query Complexity Routing](#1-adaptive-rag)
2. [Self-RAG: Self-Reflective Retrieval](#2-self-rag)
3. [CRAG: Corrective Retrieval](#3-crag)
4. [Speculative RAG: Parallel Draft-Verify](#4-speculative-rag)
5. [Stop-RAG / Adaptive Stopping](#5-stop-rag)
6. [MCTS-RAG: Tree Search over Retrieval Paths](#6-mcts-rag)
7. [RL-Based Retrieval Policies](#7-rl-based-retrieval-policies)
8. [Modular / Composable RAG Frameworks](#8-modular-rag)
9. [Mixture-of-Experts for Retrieval](#9-moe-retrieval)
10. [Router/Classifier Architectures](#10-router-classifier-architectures)
11. [DRAGIN: Real-Time Information Needs](#11-dragin)
12. [SParC-RAG: Adaptive Sequential-Parallel Scaling](#12-sparc-rag)
13. [Synthesis: MoRE Architecture Design](#13-more-architecture-design)

---

## 1. Adaptive-RAG

**Paper**: Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity
**ArXiv**: [2403.14403](https://arxiv.org/abs/2403.14403)
**Venue**: NAACL 2024
**Code**: [github.com/starsuzi/Adaptive-RAG](https://github.com/starsuzi/Adaptive-RAG)

### Key Innovation

A lightweight **query complexity classifier** that dynamically routes queries to one of three retrieval strategies, avoiding unnecessary computation on simple queries while ensuring complex queries get iterative multi-hop treatment.

### Architecture

```
Query --> T5-Large Classifier --> Route Decision
                                    |
                          +---------+---------+
                          |         |         |
                       Level A   Level B   Level C
                      (No RAG)  (Single)  (Multi-step)
                          |         |         |
                      LLM(q)   LLM(q,d)  LLM(q,d,c)
```

**Three Complexity Levels:**

| Level | Strategy | When Used |
|-------|----------|-----------|
| **A - No Retrieval** | Direct LLM answer `LLM(q)` | Simple factual queries the LLM knows |
| **B - Single-step** | One retrieval cycle `LLM(q, d)` | Moderate queries needing one fact lookup |
| **C - Multi-step** | Iterative retrieval + reasoning `LLM(q, d, c)` | Complex multi-hop reasoning queries |

### Classifier Training

- **Model**: T5-Large (770M params), though 60M models show comparable performance
- **Label Generation**: Automatic silver labels from model predictions:
  1. Run all three strategies on each query
  2. If all three answer correctly, assign simplest applicable level (A)
  3. If only B+C correct, assign B; if only C correct, assign C
  4. For unlabeled queries, use dataset inductive bias (single-hop datasets -> B, multi-hop -> C)
- **Training**: 400 sampled queries per dataset, cross-entropy loss, AdamW (lr=3e-5)
- **Classifier Accuracy**: ~54.5% overall (3-way), with most confusion between B and C (31% misclassification)

### Performance

| Setting | F1 Score | Avg Retrieval Steps |
|---------|----------|---------------------|
| Always Multi-step | 48.85 | 2.81 |
| **Adaptive-RAG** | **46.94** | **1.08** |
| Oracle (perfect routing) | 56.28 | -- |

Key insight: **2.6x fewer retrieval steps** with only 2 F1 points lost vs. always-multi-step, and significant room for improvement (oracle gap of ~9 F1 points).

### Ablations

- Without inductive bias labels: F1 drops 3.5 points (43.43)
- Classifier size has minimal impact (60M vs 770M parameters)
- Featured in LlamaIndex, LangChain, and LangGraph

### MoRE Relevance

This is the **foundational routing pattern** for MoRE. The classifier concept generalizes to routing across N expert retrievers instead of just 3 fixed strategies. The low classifier accuracy (54.5%) suggests significant room for improvement with better features or architectures.

---

## 2. Self-RAG

**Paper**: Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection
**ArXiv**: [2310.11511](https://arxiv.org/abs/2310.11511)
**Venue**: ICLR 2024 (Oral, top 1%)
**Code**: [github.com/AkariAsai/self-rag](https://github.com/AkariAsai/self-rag)

### Key Innovation

The LLM itself learns to emit **special reflection tokens** that control retrieval decisions, relevance assessment, and answer quality evaluation -- all within a single model, with no external classifier needed.

### Architecture

```
Query --> LLM generates -->  [Retrieve] token?
                               |
                     +---------+---------+
                     | Yes               | No
                     v                   v
              Retrieve k docs      Continue generating
                     |
              For each doc d_i:
                     |
              [ISREL] relevant?
                     |
              Generate response segment
                     |
              [ISSUP] supported by evidence?
                     |
              [ISUSE] overall utility score
                     |
              Segment-level beam search
              (select best continuation)
```

**Four Reflection Token Types:**

| Token | Purpose | Values |
|-------|---------|--------|
| **Retrieve** | Should I retrieve right now? | `{yes, no, continue}` |
| **ISREL** | Is retrieved document relevant to query? | `{relevant, irrelevant}` |
| **ISSUP** | Does evidence support the generation? | `{fully supported, partially supported, no support}` |
| **ISUSE** | Overall utility of the response | `{5, 4, 3, 2, 1}` (5 = best) |

### Training Process

1. **Critic Model Training**: GPT-4 generates reflection token annotations for instruction-output pairs
2. **Retriever**: Standard retriever (Contriever-MS MARCO) finds documents
3. **Generator Training**: LLM (Llama-2 7B/13B) fine-tuned with standard next-token prediction on text interleaved with reflection tokens
4. No RLHF needed -- reflection tokens are learned via supervised training

### Inference: Segment-Level Beam Search

- Generation proceeds segment by segment (not token by token)
- At each segment boundary, beam search uses **linear interpolation of critique token probabilities** as scoring function
- Users can adjust retrieval frequency at inference time by tuning the probability threshold for the `Retrieve` token
- Controllable trade-off: more retrieval = better factuality, less retrieval = lower latency

### Performance

- Self-RAG 7B/13B outperforms ChatGPT on open-domain QA, reasoning, and fact verification
- Significant gains in **citation accuracy** for long-form generation
- Outperforms retrieval-augmented Llama2-chat across all tasks

### MoRE Relevance

Self-RAG's reflection tokens provide **per-step quality signals** that a MoRE orchestrator could use to:
- Decide which expert's output to trust (using ISSUP scores)
- Trigger fallback to alternative experts (when ISREL indicates poor retrieval)
- Implement adaptive stopping (when ISUSE is high enough)

The segment-level beam search pattern generalizes to **expert-level beam search** in MoRE: run multiple experts, score their outputs with reflection-style critics, select best.

---

## 3. CRAG (Corrective RAG)

**Paper**: Corrective Retrieval Augmented Generation
**ArXiv**: [2401.15884](https://arxiv.org/abs/2401.15884)
**Venue**: AAAI 2025
**Code**: [github.com/HuskyInSalt/CRAG](https://github.com/HuskyInSalt/CRAG)

### Key Innovation

A **lightweight retrieval evaluator** that scores retrieved documents and triggers one of three corrective actions: refine, web search, or both. Plug-and-play design that wraps any existing RAG pipeline.

### Architecture

```
Query --> Retriever --> Retrieved Docs
                            |
                    Retrieval Evaluator
                    (T5-Large, 0.77B)
                            |
               +------------+------------+
               |            |            |
           Confidence    Confidence    Confidence
           > upper θ     < lower θ    in between
               |            |            |
           [CORRECT]    [INCORRECT]   [AMBIGUOUS]
               |            |            |
           Refine docs   Web Search   Refine + Web
               |            |            |
           Decompose-   ChatGPT       Both paths
           Recompose     rewrite       combined
               |         to keywords        |
               v            |            v
           Refined      Web results   Merged
           knowledge    as knowledge  knowledge
               |            |            |
               +------+-----+------+-----+
                      |            |
                   Generator (LLM)
                      |
                   Response
```

**Three Confidence Actions:**

| Confidence Level | Threshold | Action |
|------------------|-----------|--------|
| **CORRECT** | Score > upper threshold | Refine retrieved docs only |
| **INCORRECT** | All scores < lower threshold | Discard docs, use web search |
| **AMBIGUOUS** | Between thresholds | Combine refined docs + web results |

### Retrieval Evaluator

- **Architecture**: T5-Large fine-tuned on relevance signals (0.77B params)
- **Efficiency**: 10x smaller than Self-RAG's Llama-2 7B evaluator
- **Evaluation**: Per-document relevance scoring, then aggregate confidence

### Decompose-Then-Recompose Algorithm

1. Segment documents into **fine-grained knowledge strips** (sentence-level or sub-sentence)
2. Score each strip's relevance to the query using the evaluator
3. Filter out irrelevant strips
4. Recompose remaining strips by concatenation in original order
5. Result: **compressed, relevant-only context**

### Web Search Fallback

When retrieval is INCORRECT:
1. ChatGPT rewrites the query into **keyword-style search queries**
2. Google Search API retrieves URLs
3. Web pages are scraped and processed through the same decompose-recompose pipeline
4. External knowledge replaces or augments internal knowledge

### Performance

| Dataset | CRAG + SelfRAG-7B | Baseline SelfRAG-7B | Improvement |
|---------|-------------------|---------------------|-------------|
| PopQA | 61.8% | 54.9% | +6.9% |
| Biography | 86.2% | 81.2% | +5.0% |
| PubHealth | 74.8% | 72.4% | +2.4% |
| ARC-Challenge | 67.2% | 67.3% | -0.1% |

### MoRE Relevance

CRAG's confidence-based routing is directly applicable to MoRE:
- The evaluator acts as a **gatekeeper** that decides if an expert's output is usable
- The three-action pattern (use, discard+fallback, hedge) maps to expert selection
- The decompose-recompose algorithm can filter outputs from multiple experts
- Plug-and-play design means it can wrap any MoRE expert

---

## 4. Speculative RAG

**Paper**: Speculative RAG: Enhancing Retrieval Augmented Generation through Drafting
**ArXiv**: [2407.08223](https://arxiv.org/abs/2407.08223)
**Venue**: ICML 2024

### Key Innovation

Applies **speculative execution** from CPU architecture to RAG: a small specialist model generates multiple draft answers in parallel from different document subsets, then a large generalist model verifies the best draft in a single pass.

### Architecture

```
Query + Retrieved Docs
         |
    Document Clustering
    (by content similarity)
         |
    ┌────┼────┬────┐
    v    v    v    v
  Subset Subset Subset Subset
    A     B     C     D
    |     |     |     |
  Small Small Small Small   (Parallel, specialist LM)
  Model Model Model Model
    |     |     |     |
  Draft Draft Draft Draft
  + Rationale each
    |     |     |     |
    └────┬┴────┬┴────┘
         |
    Large Generalist LM
    (Single verification pass)
         |
    Best Draft Selected
         |
    Final Answer
```

### Two-Phase Process

**Phase 1: Parallel Drafting (Small Specialist LM)**
- Retrieved documents clustered by content similarity
- One document sampled from each cluster to form diverse subsets
- Each subset fed to a separate instance of the specialist LM
- Each instance generates a draft answer **with rationale** (chain-of-thought)
- All drafts generated **in parallel** -- no sequential bottleneck

**Phase 2: Verification (Large Generalist LM)**
- All drafts + rationales presented to the large LM
- Single forward pass to evaluate and select the best draft
- No iterative refinement needed -- **one-shot verification**

### Key Design Decisions

- **Diverse subsets**: Different experts see different evidence, reducing position bias
- **Rationales**: Each draft explains its reasoning, making verification easier
- **Small + Large**: Computation-heavy drafting on cheap model, quality-critical verification on expensive model

### Performance

| Benchmark | Accuracy Gain | Latency Reduction |
|-----------|---------------|-------------------|
| PubHealth | **+12.97%** | **-50.83%** |
| TriviaQA | SOTA | Improved |
| MuSiQue | SOTA | Improved |
| PopQA | SOTA | Improved |
| ARC-Challenge | SOTA | Improved |

### MoRE Relevance

This is the **closest existing architecture to MoRE**:
- Multiple "expert" models generate candidates from different evidence subsets
- A "judge" model selects the best output
- Directly maps to: N retrieval experts produce results, fusion/verification layer selects best
- The document clustering strategy could be replaced by expert-specific retrieval strategies
- Parallel execution is key to maintaining latency

---

## 5. Stop-RAG: Adaptive Stopping

**Paper**: Stop-RAG: Value-Based Retrieval Control for Iterative RAG
**ArXiv**: [2510.14337](https://arxiv.org/abs/2510.14337)
**Published**: October 2025

### Key Innovation

Casts iterative RAG as a **finite-horizon Markov Decision Process** and trains a value-based controller (DeBERTa-v3-large) to decide when additional retrieval will actually help, avoiding both under-retrieval and over-retrieval.

### MDP Formulation

| MDP Component | Definition |
|---------------|------------|
| **State s_t** | `{Q_0, A_0, q_1, d_1, a_1, ..., q_t, d_t, a_t}` -- full interaction history |
| **Actions** | `{STOP, CONT}` -- terminate or retrieve again |
| **Transition** | CONT: stochastic (depends on retrieval result); STOP: deterministic to terminal |
| **Reward** | F1 score vs ground truth, assigned only at terminal states |
| **Horizon** | Finite, max T iterations |

### Value-Based Controller

- **Backbone**: DeBERTa-v3-large
- **Architecture**: Two separate feed-forward heads (one per action)
- **Input**: Original question + all retrieved documents concatenated with [SEP] tokens
- **Decision Rule**: `STOP if Q_theta(s, STOP) - Q_theta(s, CONT) > margin_threshold`
- Margin threshold tuned on validation set

### Q(lambda) Training

For STOP action:
```
Q^lambda(s_t, STOP) = r(s_t, STOP)    [immediate reward of stopping now]
```

For CONT action (multi-step look-ahead):
```
Q^lambda(s_t, CONT) = (1-lambda) * sum_{n=1}^{T-t-1} lambda^{n-1} Q^(n)(s_t, CONT) + lambda^{T-t-1} Q^(T-t)(s_t, CONT)
```

Training procedure:
1. Generate complete trajectories (no early stopping) up to max iterations
2. Extract all trajectory prefixes as states
3. Compute rewards via N=8 independent answer generations per state
4. Calculate Q(lambda) targets using full-width action enumeration
5. Train via MSE loss; anneal lambda from 1.0 -> 0.1 during training

### Performance

| Dataset | Baseline (Fixed) | Stop-RAG | Gain |
|---------|-------------------|----------|------|
| MuSiQue | 34.5 EM / 44.8 F1 | **36.8 EM / 47.0 F1** | +2.3 EM |
| 2WikiMultihopQA | 64.9 EM / 73.1 F1 | **68.2 EM / 75.7 F1** | +3.3 EM |
| HotpotQA (CoRAG) | 30.9 EM | 31.5 EM | +0.6 EM |

Key finding: Biggest gains on datasets where over-retrieval introduces distracting evidence. Minimal gain when the generator is already robust to noise (fine-tuned CoRAG).

### MoRE Relevance

Stop-RAG's value-based controller provides the **"when to stop consulting experts"** signal for MoRE:
- After each expert produces results, evaluate whether additional experts would help
- The MDP framing generalizes to: state = accumulated expert outputs, action = consult next expert or stop
- DeBERTa-based controller is lightweight enough for real-time production use
- Lambda-return training handles the credit assignment problem of multi-expert cascades

---

## 6. MCTS-RAG

**Paper**: MCTS-RAG: Enhancing Retrieval-Augmented Generation with Monte Carlo Tree Search
**ArXiv**: [2503.20757](https://arxiv.org/abs/2503.20757)
**Venue**: EMNLP 2025 Findings
**Code**: [github.com/yale-nlp/MCTS-RAG](https://github.com/yale-nlp/MCTS-RAG)

### Key Innovation

Applies **Monte Carlo Tree Search** to explore multiple retrieval-reasoning paths simultaneously, with each tree node representing a reasoning state and edges representing actions (including retrieval). Enables small LMs to match GPT-4o on knowledge-intensive tasks.

### Tree Structure

```
                        Root (Query)
                       /     |      \
                     A1     A3      A4
                    /     /    \      \
                  A1    A4     A2     A5
                  |      |      |      |
                 A6    A6     A3     A6
                (ans)  (ans)   |    (ans)
                              A6
                             (ans)
```

### Six-Action Space

| Action | Description | When Used |
|--------|-------------|-----------|
| **A1**: Direct Answer | Answer immediately with current knowledge | High confidence, simple query |
| **A2**: Quick Reasoning | Single-step reasoning without retrieval | Moderate complexity |
| **A3**: Decompose Question | Break into sub-questions | Complex multi-part query |
| **A4**: Retrieval Reasoning | Retrieve then reason (standard RAG) | Knowledge gap detected |
| **A5**: Retrieval Decompose | Decompose + retrieve for each sub-question | Complex + knowledge gap |
| **A6**: Summarized Answer | Synthesize final answer from accumulated evidence | Terminal action |

### Four MCTS Phases for RAG

**1. Selection** (UCT):
```
UCT(s, a) = Q_bar(s, a) + C * sqrt(ln(N(s)) / N(s, a))
```
Balance between exploiting high-value paths and exploring uncertain ones.

**2. Expansion**: Create new child nodes by sampling actions. Retrieval actions (A4, A5) trigger a four-step subprocess:
- R1: Generate search queries upon detecting knowledge gaps
- R2: Execute retrieval (Bing Search + LangChain)
- R3: Evaluate retrieved data for relevance/consistency
- R4: Integrate refined information into reasoning state

**3. Simulation**: Rollout from expanded node to terminal state (4-16 iterations tested). Each rollout follows the action policy to completion.

**4. Backpropagation**: Rewards propagate upward:
```
Score(a_k) = sum(Reward(c_j in C(a_k))) / sum(Reward(c_j in C))
```
Final answer selected by voting, weighted by product of rewards along trajectory.

### Performance

| Dataset | Model | MCTS-RAG | Baseline | Improvement |
|---------|-------|----------|----------|-------------|
| ComplexWebQA | Llama 3.1-8B | 67.32% | ~47% | **+20%** |
| GPQA | Llama 3.1-8B | 74.25% | ~59% | **+15%** |
| FoolMeTwice | Llama 3.1-8B | 74.25% | ~64% | **+10%** |
| ComplexWebQA | Qwen2.5-7B | 61.38% | ~55% | +6% |
| GPQA | Qwen2.5-7B | 64.64% | ~55% | +10% |

Key: Small LMs (7-8B) with MCTS-RAG achieve **performance comparable to GPT-4o** on knowledge-intensive tasks.

### MoRE Relevance

MCTS provides a principled **search framework for expert selection**:
- Tree nodes = states after consulting some subset of experts
- Actions = which expert to consult next (or stop)
- Rewards = answer quality at terminal states
- UCT balances exploring new expert combinations vs. exploiting known-good ones
- Most applicable for complex queries where the optimal expert combination is not obvious
- Expensive for simple queries (overkill) -- combine with Adaptive-RAG to only use MCTS for Level C queries

---

## 7. RL-Based Retrieval Policies

### 7.1 ReSearch

**Paper**: ReSearch: Learning to Reason with Search for LLMs via Reinforcement Learning
**ArXiv**: [2503.19470](https://arxiv.org/abs/2503.19470)
**Published**: March 2025

**RL Formulation:**
- **Algorithm**: GRPO (Group Relative Policy Optimization)
- **Policy**: LLM generates interleaved `<think>`, `<search>`, `<result>` tagged sequences
- **Reward**: F1 score (answer) + format compliance bonus
- **Key**: Retrieved text is **masked in loss computation** to prevent the model from just copying retrieval results

**Results (7B model):**

| Benchmark | ReSearch | Best Baseline | Gain |
|-----------|----------|---------------|------|
| HotpotQA | 43.52% EM | 34.36% | **+9.2%** |
| 2WikiMultiHopQA | 47.59% EM | 27.92% | **+19.7%** |
| MuSiQue | 22.30% EM | 8.69% | **+13.6%** |
| Bamboogle | 42.40% EM | 24.80% | **+17.6%** |

Average improvement: **8.9% to 22.4%** across benchmarks. Trained on only MuSiQue data, generalizes to all benchmarks.

### 7.2 R3-RAG

**Paper**: R3-RAG: Learning Step-by-Step Reasoning and Retrieval for LLMs via Reinforcement Learning
**ArXiv**: [2505.23794](https://arxiv.org/abs/2505.23794)
**Venue**: EMNLP 2025 Findings

**Two-Stage Training:**
1. **Cold Start**: Supervised fine-tuning on synthetic trajectories (DeepSeek-V3 generated), 51,254 trajectories via rejection sampling
2. **RL Stage**: PPO training on 8,192 examples to explore beyond supervised distribution

**Dual Reward Design:**
- **Outcome Reward**: Answer correctness (match-based + LLM-based judgment)
- **Process Reward**: Per-step document relevance scored by LLM (0 to 1)
- **Combined**: `r(s_ij) = Val(s_ij) * (Acc(a_i) + Rel(d_ij)) + Val(s_ij) - 1`

**Action Space** (implicit, text-based):
1. Generate reasoning + retrieval query (invoke retriever)
2. Generate reasoning + final answer (terminate)
3. Malformed output (penalized)

**Results (Llama-3.1-8B + E5 retriever):**

| Benchmark | R3-RAG | IRCoT Baseline | Gain |
|-----------|--------|----------------|------|
| HotpotQA | 64.4% | 52.8% | **+11.6%** |
| 2WikiMultiHopQA | 61.0% | 40.6% | **+20.4%** |
| MuSiQue | 32.2% | 16.7% | **+15.5%** |

**Efficiency**: 22.8% fewer tokens than ReSearch at higher accuracy.
**Transferability**: Performance variance <3% across BM25, E5, and BGE retrievers.

### 7.3 RAG-RL

**Paper**: RAG-RL: Advancing Retrieval-Augmented Generation via RL and Curriculum Learning
**ArXiv**: [2503.12759](https://arxiv.org/abs/2503.12759)
**Published**: March 2025

**Key Innovation**: Curriculum learning for RL-trained RAG -- progressively increase the number of distractor documents during training.

**Reward Components:**
- **Answer Reward**: Exact match (gamma=5)
- **Citation Reward**: Recall-based passage citation scoring (gamma_correct=5, gamma_incorrect=2)
- **Format Reward**: XML tag structure compliance

**Curriculum Schedules Tested:**

| Schedule | Description | Best Performance |
|----------|-------------|------------------|
| Max | Always hardest difficulty | Moderate |
| Linear | Gradual 1->K | Good |
| **Min-Max** | **Easy first half, hard second half** | **Best** |
| Shuffled | Random difficulty order | Moderate |

**Results (Qwen2.5-7B, Min-Max curriculum):**
- HotpotQA: 74.97% answer F1, 81.25% citation F1
- MuSiQue: 55.13% answer F1, 69.27% citation F1

### 7.4 ProRAG

**Paper**: ProRAG: Process-Supervised Reinforcement Learning for Retrieval-Augmented Generation
**ArXiv**: [2601.21912](https://arxiv.org/abs/2601.21912)
**Published**: January 2026
**Code**: [github.com/lilinwz/ProRAG](https://github.com/lilinwz/ProRAG)

**Four-Stage Pipeline:**
1. **Supervised Policy Warmup**: SFT on GPT-4o synthesized trajectories with control tokens
2. **MCTS-based Process Reward Model (PRM)**: MCTS explores solution space; GPT-4o labels contrastive step pairs for logical validity (96% human agreement)
3. **PRM-Guided Reasoning Refinement**: Step-level rejection sampling fine-tuning, filtering trajectories by outcome correctness AND process validity
4. **Process-Supervised RL**: Online optimization with dual-granularity advantage

**Dual-Granularity Advantage:**
```
A_i,t,k = A_i,t,k^out + beta * A_i,t,k^proc

Where:
  A^proc = (r_step - mu_step) / sigma_step    [per-step quality]
  A^out  = (r_out - mu_out) / sigma_out        [final answer quality]
  beta   = 0.3 (optimal)
```

**Results (averaged across 5 benchmarks):**

| Method | Avg EM | Avg F1 |
|--------|--------|--------|
| Search-R1 | 38.5% | -- |
| **ProRAG** | **40.7%** | **49.2%** |
| Gain | **+2.2%** | -- |

Biggest gains on complex long-horizon tasks: +6.1% EM on 2WikiMultiHop, +2.9% on MuSiQue.

### MoRE Relevance of RL Approaches

RL-based methods provide the **training framework for learning expert routing policies**:

| Aspect | Application to MoRE |
|--------|---------------------|
| **Action Space** | Choose which expert to invoke next |
| **State** | Query + accumulated expert outputs |
| **Outcome Reward** | Final answer quality (F1/EM) |
| **Process Reward** | Per-expert output relevance score |
| **Curriculum** | Train on easy queries first (1 expert needed), then hard (N experts) |
| **GRPO/PPO** | Train lightweight router policy end-to-end |

Key insight from ProRAG: **Process rewards are critical** -- outcome-only RL leads to "process hallucinations" where the system reaches correct answers through flawed expert selection.

---

## 8. Modular / Composable RAG Frameworks

### 8.1 Modular RAG

**Paper**: Modular RAG: Transforming RAG Systems into LEGO-like Reconfigurable Frameworks
**ArXiv**: [2407.21059](https://arxiv.org/abs/2407.21059)
**Published**: July 2024

### Three-Tier Architecture

```
L1: Modules        [Indexing] [Pre-retrieval] [Retrieval] [Post-retrieval] [Generation] [Orchestration]
                       |            |              |             |              |              |
L2: Sub-modules    [Chunk Opt]  [Query Exp]   [Retriever]  [Reranker]    [LLM Gen]     [Routing]
                   [Structure]  [Query TF]    [Selection]  [Compress]    [Fine-tune]   [Scheduling]
                                [Query Constr]              [Selection]   [Verify]      [Fusion]
                       |            |              |             |              |              |
L3: Operators      Specific implementations (e.g., BM25, ColBERT, RRF, GPT-4)
```

### Six Core Modules

| Module | Sub-modules | Purpose |
|--------|-------------|---------|
| **Indexing** | Chunk optimization, structure organization | Prepare corpus |
| **Pre-retrieval** | Query expansion, transformation, construction | Improve queries |
| **Retrieval** | Retriever selection, fine-tuning | Find documents |
| **Post-retrieval** | Reranking, compression, selection | Refine results |
| **Generation** | LLM generation, fine-tuning, verification | Produce answers |
| **Orchestration** | **Routing, Scheduling, Fusion** | Control flow |

### Orchestration (Most Relevant to MoRE)

**Routing**: Directs queries to appropriate pipelines
- Metadata-based routing (domain, source type)
- Semantic routing (embedding similarity to prototype queries)
- Hybrid routing (combination)

**Scheduling**: Decides when to retrieve, continue, or halt
- Rule-based (fixed iteration count)
- LLM-based (Self-RAG style reflection)
- Knowledge-guided (confidence estimation)

**Fusion**: Aggregates results from multiple branches
- LLM fusion (feed all results to LLM for synthesis)
- Weighted ensemble (score-based combination)
- Reciprocal Rank Fusion (RRF)

### Five Flow Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| **Linear** | Sequential A -> B -> C | Naive RAG |
| **Conditional** | If-then routing | Adaptive-RAG |
| **Branching** | Parallel + merge | Speculative RAG |
| **Loop** | Iterative with termination | Self-RAG, MCTS-RAG |
| **Tuning** | End-to-end fine-tuning | RAG-RL |

### 8.2 ComposeRAG

**Paper**: ComposeRAG: A Modular and Composable RAG for Corpus-Grounded Multi-Hop QA
**ArXiv**: [2506.00232](https://arxiv.org/abs/2506.00232)
**Published**: June 2025

Decomposes RAG into **atomic, composable modules** with typed inputs/outputs:
- Question Decomposition
- Query Rewriting
- Retrieval Decision
- Answer Verification

Each module is independently implementable, upgradable, and analyzable.

### 8.3 FlexRAG

**Paper**: FlexRAG: A Flexible and Comprehensive Framework for Retrieval-Augmented Generation
**ArXiv**: [2506.12494](https://arxiv.org/abs/2506.12494)
**Published**: June 2025

Open-source framework with:
- Modular design with async functions for high-throughput
- Support for text, multimodal, and web RAG
- End-to-end pipeline from data prep to evaluation

### 8.4 FlashRAG

**Paper**: FlashRAG: A Modular Toolkit for Efficient RAG Research
**ArXiv**: [2405.13576](https://arxiv.org/abs/2405.13576)
**Published**: May 2024

Research toolkit implementing 12 advanced RAG methods as composable modules.

### MoRE Relevance

Modular RAG provides the **software architecture** for MoRE:
- Each retrieval expert is an L1 Module with specialized L2/L3 operators
- The Orchestration module with routing, scheduling, and fusion IS the MoRE controller
- The branching flow pattern IS the MoRE execution model
- Typed interfaces between modules enable expert composition
- Modular RAG's three fusion strategies (LLM, weighted ensemble, RRF) are all applicable

---

## 9. Mixture-of-Experts for Retrieval

### 9.1 MixRAG

**Paper**: MixRAG: Mixture-of-Experts Retrieval-Augmented Generation for Textual Graph Understanding
**ArXiv**: [2509.21391](https://arxiv.org/abs/2509.21391)
**Published**: September 2025

### Architecture

```
Query --> Query Encoder --> h_q
                              |
                    Gating Function
                    alpha_i(q) = softmax(phi(h_q, e_i))
                              |
              +---------------+---------------+
              |               |               |
         Entity Expert   Relation Expert  Subgraph Expert
         (embedding       (triple          (Steiner Tree
          similarity)      matching)        extraction)
              |               |               |
         Entity results  Relation results Subgraph results
              |               |               |
              +-------+-------+-------+-------+
                      |
              Soft fusion: p = sum(alpha_i * f_i(q))
                      |
              Query-aware GraphEncoder
              (dynamic message passing)
                      |
              LLM Generation
```

### Three Expert Retrievers

| Expert | Specialization | Method |
|--------|---------------|--------|
| **Entity Expert** | Entity name matching | Embedding similarity in semantic space |
| **Relation Expert** | Relational pattern matching | Triple embedding vs query embedding |
| **Subgraph Expert** | Structural context | Prize-Collecting Steiner Tree algorithm |

### Gating Function (Router)

```
alpha_i(q) = exp(phi(h_q, e_i)) / sum_j(exp(phi(h_q, e_j)))
```

Where `phi` is a bilinear matching function: `phi(h_q, e_i) = h_q^T W e_i`

This is a **soft routing** mechanism -- all experts contribute, weighted by compatibility.

### Results

| Dataset | MixRAG | G-Retriever (baseline) | Gain |
|---------|--------|------------------------|------|
| ExplaGraphs | 0.8863 | 0.8705 | +1.6% |
| SceneGraphs | 0.8712 | 0.8683 | +0.3% |
| WebQSP | 75.31 Hit@1 | 73.79 | +1.5% |

Ablation: All three experts together consistently outperform any pair or individual.

### 9.2 ExpertRAG

**Paper**: ExpertRAG: Efficient RAG with Mixture of Experts
**ArXiv**: [2504.08744](https://arxiv.org/abs/2504.08744)
**Published**: April 2025

**Theoretical framework** (no empirical results) proposing:
- Dynamic retrieval gating: model decides whether to consult external knowledge store or use internal expert
- Expert routing: specialized internal experts for different knowledge domains
- Latent probabilistic decisions for retrieval vs. parametric knowledge
- Comparison framework against Switch Transformer, Mixtral, and standard RAG

### 9.3 MoRA (Mixture-of-Experts for KG-RAG)

**Venue**: OpenReview
**Published**: 2025

- MoE framework for hop-wise KG knowledge retrieval
- Each expert guided by combination of two soft prompt types:
  - **Expert-specific soft prompt**: Specializes each expert
  - **Contextual soft prompt**: Adapts to current query context
- Ensemble across hops in multi-hop reasoning

### 9.4 RAGMoE

**Published**: 2025

Combines RAG with MoE-based parameter updating:
- Uses MEMoE (MoE-based knowledge editor) that doesn't modify original LLM params
- External knowledge absorbed through expert routing rather than context injection
- Addresses the "knowledge conflict" between parametric and retrieved knowledge

### MoRE Relevance

These papers directly inform MoRE architecture:

| Paper | MoRE Design Lesson |
|-------|-------------------|
| MixRAG | **Soft routing** (weighted combination) outperforms hard routing (single expert selection) |
| MixRAG | Bilinear gating function is simple and effective |
| MixRAG | Three complementary expert types beat any single expert |
| ExpertRAG | Gating should decide retrieve-vs-parametric, not just which retriever |
| MoRA | Per-hop expert selection enables adaptive expert switching during multi-hop |
| RAGMoE | Expert-absorbed knowledge avoids context window limitations |

---

## 10. Router/Classifier Architectures

### 10.1 RAGRouter

**Paper**: RAGRouter: Learning to Route Queries to Multiple Retrieval-Augmented Language Models
**ArXiv**: [2505.23052](https://arxiv.org/abs/2505.23052)
**Venue**: NeurIPS 2025
**Code**: [github.com/OwwO99/RAGRouter](https://github.com/OwwO99/RAGRouter)

### Architecture

```
Query --> Query Encoder (phi_Q) --> v_q
                                      |
Retrieved Docs --> Doc Encoder (phi_D) --> v_d
                                      |
                   Cross Encoder (phi_C) --> v_c
                                      |
                   Attention Fusion: v_f = Attention(v_r, v_d, v_c)
                                      |
Per-LLM:
  - LLM Knowledge Embedding (phi_K_i)      [static parametric knowledge]
  - RAG Capability Embedding (phi_R_i)      [ability to use retrieved info]
  - Updated: v_k_i' = f(phi_K_i, phi_R_i, v_d)
                                      |
Route: R(q,d) = argmax_i sim(v_q, v_k_i')
```

### Training: Dual Contrastive Learning

- **Cross-Setting Contrast (CSC)**: Compare model performance between non-RAG and RAG settings to capture knowledge representation shifts
- **Intra-Setting Contrast (ISC)**: Distinguish model capabilities within the same setting
- **Binary Classification Loss**: Direct answerable/unanswerable signal

### Results

- **64.46% average accuracy** (vs 60.85% best single LLM, +3.61%)
- Outperforms existing routing methods by **3.29-9.33%**
- Robust under noisy retrieval scenarios

### 10.2 LTRR (Learning To Rank Retrievers)

**Paper**: LTRR: Learning To Rank Retrievers for LLMs
**ArXiv**: [2506.13743](https://arxiv.org/abs/2506.13743)
**Venue**: SIGIR 2025 LiveRAG Challenge
**Code**: [github.com/kimdanny/Starlight-LiveRAG](https://github.com/kimdanny/Starlight-LiveRAG)

### Key Innovation

Frames retriever routing as a **learning-to-rank** problem rather than classification.

### Approach

- Pool of retrievers available (dense, sparse, hybrid, etc.)
- For each query, rank retrievers by expected utility gain to downstream LLM
- **No-retrieval** explicitly included as a routing option (not all queries need retrieval)
- Pairwise XGBoost achieves best performance

### Features for Ranking

- Query characteristics (length, complexity, domain)
- Retriever characteristics (type, index, latency)
- Query-retriever compatibility scores

### Results

- Pairwise XGBoost significantly outperforms best single-retriever RAG
- Answer Correctness (AC) metric most effective for training
- Competitive in SIGIR 2025 LiveRAG challenge

### 10.3 Adaptive-RAG Classifier (Revisited)

As detailed in Section 1:
- T5-Large (770M) but 60M also works
- 3-way classification: no retrieval / single-step / multi-step
- Automatic silver label generation
- ~54.5% accuracy, significant room for improvement

### 10.4 ModernBERT for Query Routing

**Reference**: Fine-tune classifier with ModernBERT (2025)

- ModernBERT achieves SOTA on classification while being **2-4x faster** than previous encoders
- Ideal for production routing where both accuracy and latency matter
- Can classify queries by: complexity, domain, type, retrieval strategy
- 22M-395M parameter range

### 10.5 Pre-Route: Proactive Routing

**Published**: 2025

Performs structured reasoning **before** answering:
- Uses lightweight metadata (document type, length, snippets)
- Task analysis, coverage estimation, information-need prediction
- Produces explainable and cost-efficient routing decisions

### MoRE Relevance

| Router Approach | Pros | Cons | MoRE Application |
|----------------|------|------|------------------|
| **Adaptive-RAG classifier** | Simple, fast | Low accuracy (54.5%) | Baseline MoRE router |
| **RAGRouter contrastive** | RAG-aware, captures knowledge shifts | Needs per-LLM embeddings | Expert capability-aware routing |
| **LTRR ranking** | Handles variable expert pool | Needs feature engineering | Rank experts by expected utility |
| **ModernBERT** | Fast, production-ready | Needs labeled data | Lightweight production classifier |
| **Pre-Route** | Explainable, metadata-driven | Additional latency | Route with confidence explanations |

---

## 11. DRAGIN: Real-Time Information Needs

**Paper**: DRAGIN: Dynamic Retrieval Augmented Generation based on the Information Needs of LLMs
**ArXiv**: [2403.10081](https://arxiv.org/abs/2403.10081)
**Venue**: ACL 2024

### Key Innovation

Determines **when** and **what** to retrieve based on the LLM's real-time information needs during generation, using entropy and attention patterns rather than static rules.

### RIND: When to Retrieve

Composite score combining three signals:
```
S_RIND(t_i) = H_i * a_max(i) * s_i

Where:
  H_i      = token entropy (uncertainty of generation)
  a_max(i) = max self-attention weight (token significance)
  s_i      = semantic filter (1 if meaningful word, 0 if stopword)
```

Retrieval triggers when `S_RIND > threshold`. The method is robust to threshold choice.

### QFS: What to Retrieve

Query Formulation based on Self-Attention:
1. For the token needing retrieval, extract attention scores from final Transformer layer
2. Identify top-n tokens receiving highest attention weights across the **entire context** (not just recent text)
3. Construct query preserving original token order

This captures the LLM's self-assessed importance of each token for generating the current position.

### Results (LLaMA2-13B)

| Dataset | DRAGIN | Best Baseline | Gain |
|---------|--------|---------------|------|
| 2WikiMultihopQA | 0.304 EM | 0.245 (SR-RAG) | +24% relative |
| HotpotQA | 0.4238 F1 | 0.3706 (SR-RAG) | +14% relative |
| StrategyQA | 0.689 Acc | 0.654 (SR-RAG) | +5% relative |

### MoRE Relevance

DRAGIN's attention-based signals can determine **which expert to consult mid-generation**:
- High entropy on domain-specific tokens -> route to domain expert
- Attention pattern analysis reveals what type of information is needed
- Real-time (token-level) expert routing during generation, not just pre-generation

---

## 12. SParC-RAG: Adaptive Sequential-Parallel Scaling

**Paper**: SParC-RAG: Adaptive Sequential-Parallel Scaling with Context Management for RAG
**ArXiv**: [2602.00083](https://arxiv.org/abs/2602.00083)
**Published**: January 2026

### Key Innovation

Coordinates **sequential depth** (iterative refinement) and **parallel width** (coverage expansion) under a unified context management mechanism. Addresses context contamination and scaling inefficiency in multi-hop RAG.

### Architecture

Multi-agent framework with:
- Specialized agents maintaining a **shared global context**
- Generates **targeted, complementary sub-queries** for parallel branches
- Explicit exit decision based on answer correctness and evidence sufficiency
- Preference-based fine-tuning for complementary parallel queries

### MoRE Relevance

SParC-RAG's sequential-parallel coordination is exactly what MoRE needs:
- **Sequential**: Cascade through experts one at a time (depth)
- **Parallel**: Run multiple experts simultaneously (width)
- **Adaptive**: Switch between sequential and parallel based on query needs
- **Context management**: Prevent contamination when merging expert outputs

---

## 13. Synthesis: MoRE Architecture Design

Based on all 25+ papers surveyed, here is the proposed **Mixture of Retrieval Experts (MoRE)** architecture.

### 13.1 Core Principles

| Principle | Source Papers | Implementation |
|-----------|--------------|----------------|
| **Soft routing** over hard routing | MixRAG, RAGRouter | Weighted expert combination, not winner-take-all |
| **Adaptive complexity** | Adaptive-RAG, Stop-RAG | Simple queries use 1 expert; complex queries use N |
| **Process supervision** | ProRAG, R3-RAG | Per-expert output quality signals, not just final answer |
| **Speculative parallelism** | Speculative RAG, SParC-RAG | Run experts in parallel, verify best result |
| **Corrective fallback** | CRAG | If primary expert fails, escalate to fallback chain |
| **Learned policies** | ReSearch, RAG-RL | Train routing policy end-to-end with RL |

### 13.2 Proposed Architecture

```
                            ┌─────────────────────────┐
                            │   Query Analysis Layer   │
                            │  (ModernBERT classifier) │
                            │                         │
                            │  Features:              │
                            │  - Complexity (A/B/C)   │
                            │  - Domain embedding     │
                            │  - Query type           │
                            │  - Entropy signal       │
                            └───────────┬─────────────┘
                                        │
                            ┌───────────v─────────────┐
                            │    MoRE Router Layer     │
                            │  (Bilinear gating +     │
                            │   learned policy)        │
                            │                         │
                            │  alpha_i = softmax(     │
                            │    phi(h_q, e_i))       │
                            │                         │
                            │  For Level A: skip all  │
                            │  For Level B: top-1     │
                            │  For Level C: top-K     │
                            └──┬───┬───┬───┬───┬──────┘
                               │   │   │   │   │
                    ┌──────────┘   │   │   │   └──────────┐
                    v              v   v   v              v
              ┌──────────┐  ┌─────────────────┐  ┌──────────────┐
              │  Dense    │  │  Sparse  │Graph │  │  Web Search  │
              │  Vector   │  │  BM25    │KG    │  │  Expert      │
              │  Expert   │  │  Expert  │Expert│  │  (fallback)  │
              └─────┬─────┘  └────┬─────┬──┘──┘  └──────┬───────┘
                    │              │     │               │
                    v              v     v               v
              ┌─────────────────────────────────────────────────┐
              │              Fusion Layer                       │
              │                                                │
              │  Strategy (selected by router):                │
              │  1. Weighted RRF: sum(alpha_i * rank_i)        │
              │  2. LLM Fusion: feed all to LLM for synthesis  │
              │  3. Speculative Verify: verify best draft      │
              └───────────────────┬─────────────────────────────┘
                                  │
              ┌───────────────────v─────────────────────────────┐
              │           Quality Gate (CRAG-style)             │
              │                                                │
              │  Evaluate fused result:                         │
              │  - CORRECT: proceed to generation              │
              │  - INCORRECT: escalate (web search / retry)    │
              │  - AMBIGUOUS: augment with additional expert    │
              └───────────────────┬─────────────────────────────┘
                                  │
              ┌───────────────────v─────────────────────────────┐
              │        Adaptive Stopping Controller             │
              │        (DeBERTa, Stop-RAG style)                │
              │                                                │
              │  Q(s, STOP) vs Q(s, CONT)                      │
              │  Stop if margin > threshold                    │
              └───────────────────┬─────────────────────────────┘
                                  │
                            ┌─────v─────┐
                            │ Generator │
                            └───────────┘
```

### 13.3 Expert Pool (Extensible)

| Expert | Type | Specialization | When Selected |
|--------|------|---------------|---------------|
| **Dense Vector** | Retriever | Semantic similarity, general knowledge | Default for most queries |
| **Sparse BM25** | Retriever | Keyword/entity matching, exact terms | Technical queries, proper nouns |
| **Graph KG** | Retriever | Relational reasoning, entity linking | Multi-hop, "how does X relate to Y" |
| **Table/SQL** | Retriever | Structured data, numerical queries | "What is the revenue of..." |
| **Web Search** | Retriever | Current events, out-of-corpus | Fallback, recency-sensitive queries |
| **Multimodal** | Retriever | Images, charts, diagrams | Visual document queries |
| **Code** | Retriever | Code snippets, API docs | Programming queries |

### 13.4 Router Training Strategy

Based on research findings, recommended training approach:

**Phase 1: Bootstrap (Adaptive-RAG style)**
- Generate silver labels by running each expert on evaluation queries
- Train ModernBERT classifier on complexity + expert selection labels
- Simple, fast, gets to ~55% routing accuracy

**Phase 2: Learning-to-Rank (LTRR style)**
- For each query, rank experts by downstream answer quality
- Train pairwise XGBoost or neural ranker on query-expert features
- Include "no retrieval" as explicit option

**Phase 3: RL Fine-tuning (ReSearch/ProRAG style)**
- Train routing policy end-to-end with GRPO
- Outcome reward: final answer quality
- Process reward: per-expert output relevance
- Curriculum: easy queries (1 expert) -> hard queries (N experts)

### 13.5 Fusion Strategies by Complexity

| Query Complexity | Experts Used | Fusion Strategy | Latency |
|-----------------|--------------|-----------------|---------|
| **Level A** (Simple) | 0-1 | Direct answer or single expert | ~100ms |
| **Level B** (Moderate) | 1-2 | Weighted RRF of top-2 experts | ~300ms |
| **Level C** (Complex) | 2-4 | Speculative parallel + LLM verify | ~800ms |
| **Level C+** (Multi-hop) | 2-4 per hop | MCTS over expert selection paths | ~2000ms |

### 13.6 Key Implementation Components for Pipeline Service

Based on this research, the following new components would be needed in the pipeline service:

| Component | Type | Based On | Priority |
|-----------|------|----------|----------|
| **MoRE Router** | Agent | Adaptive-RAG + MixRAG gating | **CRITICAL** |
| **Expert Pool Manager** | Agent | Modular RAG orchestration | **CRITICAL** |
| **Retrieval Quality Gate** | Agent | CRAG evaluator | **HIGH** |
| **Expert Fusion** | Post-retrieval | RRF + LLM fusion + Speculative verify | **HIGH** |
| **Adaptive Stop Controller** | Agent | Stop-RAG MDP | **HIGH** |
| **Router Trainer** | Training | LTRR + RL pipeline | **MEDIUM** |
| **Expert Capability Embeddings** | Index | RAGRouter contrastive | **MEDIUM** |
| **DRAGIN Trigger** | Agent | Entropy + attention signals | **LOW** |
| **MCTS Expert Selector** | Agent | MCTS-RAG action space | **LOW** |

### 13.7 Performance Expectations

Based on paper results, a well-implemented MoRE system should achieve:

| Metric | Single Best Expert | MoRE (Expected) | Basis |
|--------|-------------------|-----------------|-------|
| Accuracy | Baseline | +3-10% | MixRAG (+1.5%), RAGRouter (+3.6%), MCTS-RAG (+15-20%) |
| Latency (simple) | ~200ms | ~120ms (skip retrieval) | Adaptive-RAG (2.6x fewer retrievals) |
| Latency (complex) | ~500ms | ~800ms (parallel experts) | Speculative RAG (50% reduction vs sequential) |
| Retrieval calls | Fixed N | 40% fewer | Stop-RAG |
| Robustness | Fails on OOD | Fallback to web/other expert | CRAG |

---

## References

### Core Routing & Adaptation
- Adaptive-RAG, arXiv:2403.14403, NAACL 2024
- Self-RAG, arXiv:2310.11511, ICLR 2024 (Oral)
- CRAG, arXiv:2401.15884, AAAI 2025
- Speculative RAG, arXiv:2407.08223, ICML 2024
- Stop-RAG, arXiv:2510.14337, October 2025
- DRAGIN, arXiv:2403.10081, ACL 2024

### Tree Search & RL
- MCTS-RAG, arXiv:2503.20757, EMNLP 2025 Findings
- ReSearch, arXiv:2503.19470, March 2025
- R3-RAG, arXiv:2505.23794, EMNLP 2025 Findings
- RAG-RL, arXiv:2503.12759, March 2025
- ProRAG, arXiv:2601.21912, January 2026

### MoE & Ensemble Retrieval
- MixRAG, arXiv:2509.21391, September 2025
- ExpertRAG, arXiv:2504.08744, April 2025
- RAGMoE, 2025 (SSRN)
- MoRA, OpenReview 2025

### Modular Frameworks
- Modular RAG, arXiv:2407.21059, July 2024
- ComposeRAG, arXiv:2506.00232, June 2025
- FlexRAG, arXiv:2506.12494, June 2025
- FlashRAG, arXiv:2405.13576, May 2024

### Router Architectures
- RAGRouter, arXiv:2505.23052, NeurIPS 2025
- LTRR, arXiv:2506.13743, SIGIR 2025
- SParC-RAG, arXiv:2602.00083, January 2026

### Supplementary
- Modular RAG Survey, arXiv:2407.21059
- Agentic RAG Survey, arXiv:2501.09136
- RAG Comprehensive Survey, arXiv:2506.00054
