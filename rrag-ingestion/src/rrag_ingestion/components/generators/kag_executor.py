from __future__ import annotations

import logging
import subprocess
import sys
import tempfile

from rrag_ingestion.components.generators.base import BaseGenerator
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class KAGMathExecutor(BaseGenerator):
    """Python-based mathematical computation executor from KAG."""

    name = "kag.math_executor"
    version = "0.1.0"
    description = "LLM-generated Python code execution for mathematical operations (from KAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "timeout_seconds": {"type": "integer", "default": 5},
        "max_retries": {"type": "integer", "default": 3},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        context = input_data.data.get("answer", "") or input_data.data.get("context", "")

        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for math execution"])

        model = config.get("llm_model", "gpt-4o-mini")
        timeout = config.get("timeout_seconds", 5)
        max_retries = config.get("max_retries", 3)

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            error_context = ""
            for attempt in range(max_retries):
                code_prompt = (
                    f"Write Python code to solve the following problem. "
                    f"Print only the final numerical answer.\n\n"
                    f"Context: {context}\n"
                    f"Problem: {query}\n"
                    f"{f'Previous error: {error_context}' if error_context else ''}\n\n"
                    f"Python code:"
                )

                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": code_prompt}],
                    temperature=0.0,
                )

                code = response.choices[0].message.content or ""
                # Extract code from markdown blocks if present
                if "```python" in code:
                    code = code.split("```python")[1].split("```")[0]
                elif "```" in code:
                    code = code.split("```")[1].split("```")[0]

                result, error = self._run_code(code.strip(), timeout)
                if error:
                    error_context = error
                    continue

                return ComponentResult(
                    data={**input_data.data, "answer": result, "generated_code": code.strip()},
                    metadata={"executor": "math", "attempts": attempt + 1},
                )

            return ComponentResult(
                data=input_data.data,
                errors=[f"Math execution failed after {max_retries} attempts: {error_context}"],
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Math executor failed: {e}"])

    def _run_code(self, code: str, timeout: int) -> tuple[str, str]:
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    [sys.executable, f.name],
                    capture_output=True, text=True, timeout=timeout,
                )
            if result.returncode != 0:
                return "", result.stderr.strip()
            return result.stdout.strip(), ""
        except subprocess.TimeoutExpired:
            return "", "Code execution timed out"
        except Exception as e:
            return "", str(e)


@register_component
class KAGDeduceExecutor(BaseGenerator):
    """Logical deduction executor from KAG for comparative reasoning."""

    name = "kag.deduce_executor"
    version = "0.1.0"
    description = "Logical deduction for comparative reasoning, judgement, and entailment (from KAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "deduce_type": {
            "type": "string",
            "default": "judgement",
            "enum": ["choice", "multi_choice", "entailment", "judgement", "extract"],
        },
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        context = input_data.data.get("answer", "") or input_data.data.get("context", "")
        retrieved = input_data.data.get("retrieved", [])

        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for deduction"])

        model = config.get("llm_model", "gpt-4o-mini")
        deduce_type = config.get("deduce_type", "judgement")

        doc_context = "\n".join(
            doc.content if hasattr(doc, "content") else doc.get("content", "")
            for doc in retrieved[:5]
        )
        full_context = f"{context}\n{doc_context}".strip()

        prompt_map = {
            "judgement": f"Based on the evidence, determine if the following is true or false.\n\nEvidence:\n{full_context}\n\nStatement: {query}\n\nAnswer (True/False with explanation):",
            "choice": f"Based on the evidence, select the best answer.\n\nEvidence:\n{full_context}\n\nQuestion: {query}\n\nAnswer:",
            "entailment": f"Does the evidence support, contradict, or is neutral to the claim?\n\nEvidence:\n{full_context}\n\nClaim: {query}\n\nAnswer (supports/contradicts/neutral with explanation):",
            "extract": f"Extract the specific answer from the evidence.\n\nEvidence:\n{full_context}\n\nQuestion: {query}\n\nExtracted Answer:",
            "multi_choice": f"Based on the evidence, select all correct answers.\n\nEvidence:\n{full_context}\n\nQuestion: {query}\n\nAnswers:",
        }

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_map.get(deduce_type, prompt_map["judgement"])}],
                temperature=0.0,
            )

            answer = response.choices[0].message.content or ""

            return ComponentResult(
                data={**input_data.data, "answer": answer},
                metadata={"executor": "deduce", "deduce_type": deduce_type},
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Deduction failed: {e}"])
