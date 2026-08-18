"""Agentic RAG Retrieval composite component.

Six-step pipeline with an evaluate-and-loop pattern:
1. Analyze Query -- understand intent and extract keywords
2. Plan Retrieval Strategy -- LLM decides which tools to call
3. Execute Tools -- dispatch tool calls to storage layer
4. Assemble Evidence -- collect and deduplicate results
5. Evaluate & Decide -- check sufficiency; loop back to step 2 if not
6. Generate Answer -- produce the final grounded response
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pipeline_service.framework import component, step, CompositeComponent

logger = logging.getLogger(__name__)


@component(
    category="agent",
    name="Agentic RAG Retrieval",
    description=(
        "Agent-loop retrieval: analyzes the query, plans a retrieval strategy "
        "using available tools, executes them, evaluates evidence sufficiency, "
        "and iterates until a comprehensive answer can be generated."
    ),
    input_ports=[
        {"name": "query", "type": "str"},
    ],
    output_ports=[
        {"name": "answer", "type": "str"},
        {"name": "context", "type": "dict"},
        {"name": "trace", "type": "dict"},
    ],
)
class AgenticRAGRetrieval(CompositeComponent):

    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "Workspace scope key",
            },
            "max_iterations": {
                "type": "integer",
                "default": 3,
                "description": "Max agent loop iterations before forced generation",
            },
            "generation_model": {
                "type": "string",
                "default": "gpt-4o-mini",
            },
            "planning_model": {
                "type": "string",
                "default": "gpt-4o-mini",
            },
            "embedding_model": {
                "type": "string",
                "default": "text-embedding-3-small",
            },
            "max_entity_tokens": {
                "type": "integer",
                "default": 4000,
            },
            "max_relation_tokens": {
                "type": "integer",
                "default": 4000,
            },
            "max_total_tokens": {
                "type": "integer",
                "default": 12000,
            },
            "response_type": {
                "type": "string",
                "default": "Multiple Paragraphs",
            },
            "language": {
                "type": "string",
                "default": "English",
            },
        },
        "required": ["scope"],
    }

    # ------------------------------------------------------------------
    # Step 1: Analyze Query
    # ------------------------------------------------------------------

    @step(order=1, name="Analyze Query", description="Understand query intent and extract keywords")
    async def analyze_query(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..extraction import _call_llm
        from ..prompts import KEYWORD_EXTRACTION_PROMPT
        from ..agent.trace import AgentTrace

        query = data.get("query", "")
        language = config.get("language", "English")
        model = config.get("planning_model", "gpt-4o-mini")

        prompt = KEYWORD_EXTRACTION_PROMPT.format(query=query, language=language)
        raw = await _call_llm(prompt, model)

        hl_keywords: list[str] = []
        ll_keywords: list[str] = []
        if raw:
            try:
                parsed = json.loads(raw)
                hl_keywords = parsed.get("high_level_keywords", [])
                ll_keywords = parsed.get("low_level_keywords", [])
            except (json.JSONDecodeError, TypeError):
                pass

        # Initialise trace and cumulative evidence stores
        trace = AgentTrace(query=query)

        return {
            "hl_keywords": hl_keywords,
            "ll_keywords": ll_keywords,
            "evidence_entities": [],
            "evidence_relations": [],
            "evidence_chunks": [],
            "evidence_summary": "",
            "_trace": trace.to_dict(),
        }

    # ------------------------------------------------------------------
    # Step 2: Plan Retrieval Strategy
    # ------------------------------------------------------------------

    @step(order=2, name="Plan Retrieval Strategy", description="LLM-based selection of retrieval tools")
    async def plan_retrieval_strategy(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..agent.planner import plan_retrieval_strategy as plan
        from ..agent.trace import AgentTrace, TraceStep

        query = data.get("query", "")
        model = config.get("planning_model", "gpt-4o-mini")
        evidence_summary = data.get("evidence_summary", "")

        t0 = time.time()
        tool_calls = await plan(query, evidence_summary, model)
        duration = (time.time() - t0) * 1000

        # Record trace step
        trace_step = TraceStep(
            iteration=0,
            action="plan",
            tool_calls=[
                {"tool_name": tc.tool_name, "arguments": tc.arguments}
                for tc in tool_calls
            ],
            duration_ms=duration,
        )

        return {
            "planned_tool_calls": [
                {"tool_name": tc.tool_name, "arguments": tc.arguments}
                for tc in tool_calls
            ],
            "_trace_step_plan": trace_step.to_dict(),
        }

    # ------------------------------------------------------------------
    # Step 3: Execute Tools
    # ------------------------------------------------------------------

    @step(order=3, name="Execute Tools", description="Dispatch planned tool calls to storage layer")
    async def execute_tools(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..agent.tool_executor import execute_tool
        from ..agent.tools import ToolCall

        scope = config["scope"]
        embedding_model = config.get("embedding_model", "text-embedding-3-small")
        planned = data.get("planned_tool_calls", [])

        results_summary: list[dict[str, Any]] = []
        new_entities: list[dict] = []
        new_relations: list[dict] = []
        new_chunks: list[dict] = []

        for tc_raw in planned:
            tc = ToolCall(
                tool_name=tc_raw["tool_name"],
                arguments=tc_raw.get("arguments", {}),
            )
            result = await execute_tool(tc, scope, embedding_model)

            results_summary.append({
                "tool_name": result.tool_name,
                "success": result.success,
                "count": len(result.data),
                "error": result.error,
            })

            if not result.success:
                continue

            # Classify results by tool type
            if tc.tool_name in ("graph_entity_search", "vector_entity_search", "graph_traverse"):
                new_entities.extend(result.data)
            elif tc.tool_name == "graph_relation_search":
                new_relations.extend(result.data)
            elif tc.tool_name == "vector_chunk_search":
                new_chunks.extend(result.data)

        return {
            "new_entities": new_entities,
            "new_relations": new_relations,
            "new_chunks": new_chunks,
            "_tool_results_summary": results_summary,
        }

    # ------------------------------------------------------------------
    # Step 4: Assemble Evidence
    # ------------------------------------------------------------------

    @step(order=4, name="Assemble Evidence", description="Collect and deduplicate all evidence gathered so far")
    async def assemble_evidence(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        # Merge new results into cumulative evidence
        existing_entities = data.get("evidence_entities", [])
        existing_relations = data.get("evidence_relations", [])
        existing_chunks = data.get("evidence_chunks", [])

        new_entities = data.get("new_entities", [])
        new_relations = data.get("new_relations", [])
        new_chunks = data.get("new_chunks", [])

        # Dedup by entity_id / content
        seen_entity_ids = {e.get("entity_id", "") for e in existing_entities}
        for ent in new_entities:
            eid = ent.get("entity_id", "")
            if eid and eid not in seen_entity_ids:
                existing_entities.append(ent)
                seen_entity_ids.add(eid)

        seen_rel_keys = {
            (r.get("source_entity", ""), r.get("target_entity", ""))
            for r in existing_relations
        }
        for rel in new_relations:
            rk = (rel.get("source_entity", ""), rel.get("target_entity", ""))
            rk_rev = (rk[1], rk[0])
            if rk not in seen_rel_keys and rk_rev not in seen_rel_keys:
                existing_relations.append(rel)
                seen_rel_keys.add(rk)

        seen_content = {c.get("content", "") for c in existing_chunks}
        for chunk in new_chunks:
            content = chunk.get("content", "")
            if content and content not in seen_content:
                existing_chunks.append(chunk)
                seen_content.add(content)

        # Build evidence summary for the planner (next iteration)
        entity_names = [e.get("entity_name", "") for e in existing_entities[:10]]
        summary = (
            f"Entities ({len(existing_entities)}): {', '.join(entity_names)}. "
            f"Relations: {len(existing_relations)}. Chunks: {len(existing_chunks)}."
        )

        return {
            "evidence_entities": existing_entities,
            "evidence_relations": existing_relations,
            "evidence_chunks": existing_chunks,
            "evidence_summary": summary,
        }

    # ------------------------------------------------------------------
    # Step 5: Evaluate & Decide
    # ------------------------------------------------------------------

    @step(
        order=5,
        name="Evaluate And Decide",
        description="Check evidence sufficiency; loop back or proceed to generation",
        outputs=["Generate Answer", "Plan Retrieval Strategy"],
    )
    async def evaluate_and_decide(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..agent.evaluator import evaluate_evidence

        query = data.get("query", "")
        model = config.get("planning_model", "gpt-4o-mini")

        entities = data.get("evidence_entities", [])
        relations = data.get("evidence_relations", [])
        chunks = data.get("evidence_chunks", [])

        evaluation = await evaluate_evidence(
            query=query,
            entities=entities,
            relations=relations,
            chunks=chunks,
            model=model,
        )

        sufficient = evaluation.get("sufficient", False)

        # Route: if sufficient -> Generate Answer, else -> Plan Retrieval Strategy
        route = "Generate Answer" if sufficient else "Plan Retrieval Strategy"

        return {
            "_route": route,
            "evaluation": evaluation,
        }

    # ------------------------------------------------------------------
    # Step 6: Generate Answer
    # ------------------------------------------------------------------

    @step(order=6, name="Generate Answer", description="Generate the final answer using assembled evidence")
    async def generate_answer(
        self, data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        from ..extraction import _call_llm
        from ..prompts import RAG_RESPONSE_PROMPT
        from ..context_builder import build_context

        query = data.get("query", "")
        model = config.get("generation_model", "gpt-4o-mini")
        response_type = config.get("response_type", "Multiple Paragraphs")

        entities = data.get("evidence_entities", [])
        relations = data.get("evidence_relations", [])
        chunks = data.get("evidence_chunks", [])

        context = build_context(
            mode="agentic",
            entities=entities,
            relations=relations,
            graph_chunks=[],
            vector_chunks=chunks,
            max_entity_tokens=config.get("max_entity_tokens", 4000),
            max_relation_tokens=config.get("max_relation_tokens", 4000),
            max_total_tokens=config.get("max_total_tokens", 12000),
        )

        prompt = RAG_RESPONSE_PROMPT.format(
            response_type=response_type,
            entities_context=context.get("entities_context", "[]"),
            relations_context=context.get("relations_context", "[]"),
            chunks_context=context.get("chunks_context", "[]"),
        )

        answer = await _call_llm(query, model, system_prompt=prompt)

        return {
            "answer": answer,
            "context": context,
            "evaluation": data.get("evaluation", {}),
            "trace": data.get("_trace", {}),
        }
