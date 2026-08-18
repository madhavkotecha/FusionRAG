from __future__ import annotations

import logging

from rrag_ingestion.components.planners.base import BasePlanner
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

PLANNING_PROMPT = """You are a task planner for question answering. Decompose the query into a plan of sub-tasks.

Available executors:
- retrieval: Search knowledge base for information
- math: Perform mathematical calculations
- deduce: Make logical deductions or comparisons
- output: Format and return the final answer

For each task, output a line:
TASK|executor|query_or_instruction|depends_on(comma-separated task numbers or NONE)

Query: {query}

{context}

Plan:"""


@register_component
class KAGStaticPlanner(BasePlanner):
    """Static task DAG planner from KAG."""

    name = "kag.static_planner"
    version = "0.1.0"
    description = "Static DAG-based task planning with query decomposition (from KAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "max_tasks": {"type": "integer", "default": 5},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for planning"])

        model = config.get("llm_model", "gpt-4o-mini")
        max_tasks = config.get("max_tasks", 5)

        context = ""
        if input_data.data.get("retrieved"):
            docs = input_data.data["retrieved"][:3]
            context = "Available context:\n" + "\n".join(
                doc.content if hasattr(doc, "content") else doc.get("content", "")
                for doc in docs
            )

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            prompt = PLANNING_PROMPT.format(query=query, context=context)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            raw = response.choices[0].message.content or ""
            tasks = []
            for line in raw.strip().split("\n"):
                line = line.strip()
                if line.startswith("TASK|"):
                    parts = line.split("|")
                    if len(parts) >= 4:
                        tasks.append({
                            "executor": parts[1].strip(),
                            "instruction": parts[2].strip(),
                            "depends_on": [d.strip() for d in parts[3].split(",") if d.strip() != "NONE"],
                        })

            return ComponentResult(
                data={**input_data.data, "plan": tasks[:max_tasks]},
                metadata={"task_count": len(tasks[:max_tasks])},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Planning failed: {e}"])


@register_component
class KAGIterativePlanner(BasePlanner):
    """Iterative plan-execute-replan loop from KAG."""

    name = "kag.iterative_planner"
    version = "0.1.0"
    description = "Iterative plan-execute-replan loop for complex queries (from KAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "max_iterations": {"type": "integer", "default": 5},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for iterative planning"])

        model = config.get("llm_model", "gpt-4o-mini")
        max_iterations = config.get("max_iterations", 5)

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            context = input_data.data.get("answer", "")
            iteration_history = []

            for i in range(max_iterations):
                prompt = (
                    f"Iteration {i + 1}: Given the query and current context, decide the next action.\n\n"
                    f"Query: {query}\n"
                    f"Current answer: {context}\n"
                    f"History: {iteration_history}\n\n"
                    f"If the answer is complete, output: DONE|<final_answer>\n"
                    f"If more work needed, output: TASK|executor|instruction\n"
                    f"Executors: retrieval, math, deduce, output"
                )

                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )

                raw = response.choices[0].message.content or ""
                iteration_history.append(raw.strip())

                if raw.strip().startswith("DONE|"):
                    final = raw.strip().split("|", 1)[1] if "|" in raw else raw
                    return ComponentResult(
                        data={**input_data.data, "answer": final, "plan": iteration_history},
                        metadata={"iterations": i + 1, "status": "completed"},
                    )

            return ComponentResult(
                data={**input_data.data, "plan": iteration_history},
                metadata={"iterations": max_iterations, "status": "max_iterations_reached"},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Iterative planning failed: {e}"])
