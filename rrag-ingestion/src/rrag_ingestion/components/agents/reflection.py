from __future__ import annotations

import logging

from rrag_ingestion.components.agents.base import BaseAgent
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

REFLECTION_PROMPT = """You are a quality assurance agent. Evaluate the following answer and provide feedback.

Query: {query}
Answer: {answer}
Context used: {context}

Evaluate on:
1. Factual accuracy (does the answer match the context?)
2. Completeness (does it fully address the query?)
3. Relevance (is everything in the answer relevant?)
4. Coherence (is the answer well-structured?)

Output a JSON object:
{{
  "score": <0-10>,
  "issues": ["list of issues found"],
  "suggestions": ["list of improvement suggestions"],
  "needs_retry": <true/false>
}}"""


@register_component
class SelfReflectionAgent(BaseAgent):
    """Self-reflection agent that critiques and improves generated answers."""

    name = "agent.reflection"
    version = "0.1.0"
    description = "Self-reflection agent for answer quality evaluation and improvement"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "min_score_threshold": {"type": "number", "default": 6.0},
        "max_retries": {"type": "integer", "default": 2},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        answer = input_data.data.get("answer", "")

        if not answer:
            return ComponentResult(data=input_data.data, metadata={"reflection": "no_answer"})

        model = config.get("llm_model", "gpt-4o-mini")
        min_score = config.get("min_score_threshold", 6.0)

        retrieved = input_data.data.get("retrieved", [])
        context_summary = "\n".join(
            (doc.content if hasattr(doc, "content") else doc.get("content", ""))[:200]
            for doc in retrieved[:3]
        )

        try:
            import json
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            prompt = REFLECTION_PROMPT.format(
                query=query, answer=answer, context=context_summary
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            raw = response.choices[0].message.content or ""
            if "```" in raw:
                raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]

            reflection = json.loads(raw.strip())

            return ComponentResult(
                data={
                    **input_data.data,
                    "reflection": reflection,
                    "needs_retry": reflection.get("needs_retry", False) or reflection.get("score", 10) < min_score,
                },
                metadata={
                    "reflection_score": reflection.get("score", 0),
                    "issues_count": len(reflection.get("issues", [])),
                },
            )

        except Exception as e:
            return ComponentResult(
                data={**input_data.data, "reflection": {"error": str(e)}},
                errors=[f"Reflection failed: {e}"],
            )
