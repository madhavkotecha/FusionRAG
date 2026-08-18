"""Prompt templates ported from LightRAG/lightrag/prompt.py.

These are the key prompts used by the extraction, retrieval, and generation
steps of the LightRAG pipeline.  Templates use Python ``str.format``
placeholders.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Delimiters
# ---------------------------------------------------------------------------

TUPLE_DELIMITER = "<|#|>"
COMPLETION_DELIMITER = "<|COMPLETE|>"

# ---------------------------------------------------------------------------
# Entity / relation extraction
# ---------------------------------------------------------------------------

ENTITY_EXTRACTION_SYSTEM_PROMPT = """\
---Role---
You are a Knowledge Graph Specialist responsible for extracting entities and \
relationships from the input text.

---Instructions---
1.  **Entity Extraction & Output:**
    *   Identify clearly defined and meaningful entities in the input text.
    *   For each entity extract:
        *   `entity_name`: Title-cased, consistent across the extraction.
        *   `entity_type`: One of: {entity_types}.  Use `Other` if none fit.
        *   `entity_description`: Concise description based solely on the text.
    *   Output format (4 fields delimited by `{tuple_delimiter}`):
        entity{tuple_delimiter}entity_name{tuple_delimiter}entity_type{tuple_delimiter}entity_description

2.  **Relationship Extraction & Output:**
    *   Identify direct, clearly stated relationships between extracted entities.
    *   Decompose N-ary relationships into binary pairs.
    *   For each relationship extract:
        *   `source_entity`, `target_entity` (consistent naming, title-cased)
        *   `relationship_keywords`: comma-separated high-level keywords
        *   `relationship_description`: concise explanation
    *   Output format (5 fields):
        relation{tuple_delimiter}source_entity{tuple_delimiter}target_entity{tuple_delimiter}relationship_keywords{tuple_delimiter}relationship_description

3.  Output all entities first, then relationships (most significant first).
4.  Use third person; avoid pronouns.  Output in {language}.
5.  Output `{completion_delimiter}` as the final line.
"""

ENTITY_EXTRACTION_USER_PROMPT = """\
---Task---
Extract entities and relationships from the text below.

<Entity_types>
[{entity_types}]

<Input Text>
```
{input_text}
```

<Output>
"""

ENTITY_CONTINUE_EXTRACTION_PROMPT = """\
---Task---
Identify any missed or incorrectly formatted entities and relationships from \
the previous extraction.  Do NOT repeat already-correct items.

Output `{completion_delimiter}` as the final line.

<Output>
"""

# ---------------------------------------------------------------------------
# Keyword extraction (for retrieval)
# ---------------------------------------------------------------------------

KEYWORD_EXTRACTION_PROMPT = """\
---Role---
You are an expert keyword extractor for a RAG system.

---Goal---
Given a user query, extract two types of keywords:
1. **high_level_keywords**: overarching concepts, themes, core intent.
2. **low_level_keywords**: specific entities, proper nouns, technical terms.

---Constraints---
* Output MUST be a valid JSON object with keys "high_level_keywords" and \
"low_level_keywords", each containing a list of strings.
* No markdown fences, no explanatory text -- just the JSON object.
* All keywords in {language}.
* For vague or nonsensical queries return empty lists.

---Examples---
Query: "How does international trade influence global economic stability?"
Output:
{{"high_level_keywords": ["International trade", "Global economic stability", \
"Economic impact"], "low_level_keywords": ["Trade agreements", "Tariffs", \
"Currency exchange", "Imports", "Exports"]}}

---Real Data---
User Query: {query}

Output:"""

# ---------------------------------------------------------------------------
# RAG response generation
# ---------------------------------------------------------------------------

RAG_RESPONSE_PROMPT = """\
---Role---
You are an expert AI assistant synthesizing information from a provided \
knowledge base.  Answer ONLY using the **Context** below.

---Goal---
Generate a comprehensive, well-structured answer integrating relevant facts \
from the Knowledge Graph Data and Document Chunks in the Context.

---Instructions---
1. Identify all context pieces relevant to the query.
2. Weave facts into a coherent response; use your own knowledge only for \
   fluent phrasing -- NOT for new information.
3. If the answer cannot be found in the context, state that clearly.
4. Use Markdown formatting.  Response type: {response_type}.
5. Respond in the same language as the query.

---Context---

Knowledge Graph Data (Entities):

```json
{entities_context}
```

Knowledge Graph Data (Relationships):

```json
{relations_context}
```

Document Chunks:

```json
{chunks_context}
```
"""

# ---------------------------------------------------------------------------
# Entity description summarisation
# ---------------------------------------------------------------------------

SUMMARIZE_ENTITY_DESCRIPTIONS_PROMPT = """\
---Role---
You are a Knowledge Graph Specialist.

---Task---
Synthesize the following descriptions of "{description_name}" ({description_type}) \
into a single comprehensive summary.  Integrate ALL key facts; write in third \
person; keep under {summary_max_tokens} tokens.  Output in {language}.

Description List:
```
{description_list}
```

---Output---
"""
