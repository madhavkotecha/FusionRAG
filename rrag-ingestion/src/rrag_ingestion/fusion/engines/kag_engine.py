"""ADR-0007: KAG Engine — logical-form-guided hybrid reasoning.

Five operator types (executed in sequence from the logical plan):
  Retrieval  → fetch relevant chunks/entities from stores
  Sort       → rank/filter results by a criterion
  Math       → compute numerical expressions (sandboxed eval)
  Deduce     → derive new facts using LLM reasoning over evidence
  Output     → format and return the final answer
"""
from __future__ import annotations

import ast
import logging
import operator
import re
from dataclasses import dataclass, field
from typing import Any

from rrag_ingestion.fusion.engines.base import EngineResult
from rrag_ingestion.fusion.knowledge_store import KnowledgeStore

logger = logging.getLogger(__name__)

_PLAN_PROMPT = """\
Decompose the following question into a logical execution plan using these operators:
RETRIEVAL(query) - retrieve evidence for a sub-question
SORT(field, order) - sort evidence by a field (asc/desc)
MATH(expression) - compute a mathematical expression using variables from prior steps
DEDUCE(claim) - reason from gathered evidence to derive a conclusion
OUTPUT(format) - produce the final answer

Question: {query}

Output each step on its own line as: OPERATOR|argument
Example:
RETRIEVAL|What is the annual revenue of OpenAI?
SORT|revenue,desc
MATH|revenue_2023 - revenue_2022
DEDUCE|Has revenue grown year over year?
OUTPUT|summary"""

_DEDUCE_PROMPT = """\
Given the following evidence, derive a conclusion for the claim below.
Be concise and factual.

Claim: {claim}

Evidence:
{evidence}

Conclusion:"""


@dataclass
class KAGStep:
    op: str
    arg: str
    result: Any = None


class _SafeMathEvaluator(ast.NodeVisitor):
    """Evaluate simple arithmetic expressions without exec()."""

    _ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(self, variables: dict[str, float]) -> None:
        self._vars = variables

    def evaluate(self, expr: str) -> float:
        # Replace variable names with their values before parsing
        for name, val in self._vars.items():
            expr = re.sub(r"\b" + re.escape(name) + r"\b", str(val), expr)
        tree = ast.parse(expr.strip(), mode="eval")
        return self.visit(tree.body)

    def visit_BinOp(self, node: ast.BinOp) -> float:
        return self._ops[type(node.op)](self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        return self._ops[type(node.op)](self.visit(node.operand))

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Non-numeric constant: {node.value}")

    def generic_visit(self, node: ast.AST) -> None:
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")


class KAGEngine:
    """Logical-form-guided reasoning engine with 5 operator types."""

    name = "kag"

    def __init__(self, store: KnowledgeStore, llm_client: object | None = None) -> None:
        self._store = store
        self._llm = llm_client

    def _get_llm(self) -> object:
        if self._llm is not None:
            return self._llm
        from rrag_ingestion.services.openai_client import get_openai_client
        return get_openai_client()

    async def _build_logical_plan(self, query: str, model: str) -> list[KAGStep]:
        client = self._get_llm()
        prompt = _PLAN_PROMPT.format(query=query)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        raw = resp.choices[0].message.content or ""
        steps = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if "|" in line:
                parts = line.split("|", 1)
                op = parts[0].strip().upper()
                arg = parts[1].strip() if len(parts) > 1 else ""
                if op in ("RETRIEVAL", "SORT", "MATH", "DEDUCE", "OUTPUT"):
                    steps.append(KAGStep(op=op, arg=arg))
        return steps

    async def _execute_retrieval(
        self,
        arg: str,
        datastore_id: str,
        top_k: int,
        embedding: list[float] | None,
    ) -> list[dict]:
        chunks = self._store.search_bm25(arg, top_k=top_k)
        if embedding is not None:
            try:
                vec = self._store.search_vectors(embedding, top_k=top_k)
                chunks.extend(vec)
            except Exception as e:
                logger.warning(f"KAG vector retrieval failed: {e}")
        return chunks

    def _execute_sort(self, arg: str, evidence: list[dict]) -> list[dict]:
        parts = arg.split(",")
        field_name = parts[0].strip() if parts else "score"
        order = parts[1].strip().lower() if len(parts) > 1 else "desc"
        reverse = order != "asc"
        return sorted(evidence, key=lambda x: x.get(field_name, x.get("score", 0)), reverse=reverse)

    def _execute_math(self, arg: str, variables: dict[str, float]) -> float:
        try:
            evaluator = _SafeMathEvaluator(variables)
            return evaluator.evaluate(arg)
        except Exception as e:
            logger.warning(f"KAG MATH failed for '{arg}': {e}")
            return float("nan")

    async def _execute_deduce(
        self, claim: str, evidence: list[dict], model: str
    ) -> str:
        client = self._get_llm()
        evidence_text = "\n".join(f"- {c['content'][:300]}" for c in evidence[:5])
        prompt = _DEDUCE_PROMPT.format(claim=claim, evidence=evidence_text)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=256,
        )
        return (resp.choices[0].message.content or "").strip()

    async def retrieve(
        self,
        query: str,
        datastore_id: str,
        top_k: int = 20,
        model: str = "gpt-4o-mini",
        embedding: list[float] | None = None,
    ) -> EngineResult:
        all_chunks: list[dict] = []
        deductions: list[str] = []
        math_vars: dict[str, float] = {}
        answer = ""

        try:
            steps = await self._build_logical_plan(query, model)
        except Exception as e:
            logger.warning(f"KAG plan building failed: {e}")
            # Fallback: single retrieval step
            steps = [KAGStep(op="RETRIEVAL", arg=query)]

        for i, step in enumerate(steps):
            try:
                if step.op == "RETRIEVAL":
                    chunks = await self._execute_retrieval(
                        step.arg, datastore_id, top_k, embedding
                    )
                    for c in chunks:
                        c["metadata"] = {**c.get("metadata", {}), "engine": "kag", "kag_step": i}
                    all_chunks.extend(chunks)
                    step.result = chunks

                elif step.op == "SORT":
                    all_chunks = self._execute_sort(step.arg, all_chunks)
                    step.result = all_chunks

                elif step.op == "MATH":
                    val = self._execute_math(step.arg, math_vars)
                    step.result = val
                    math_vars[f"step{i}"] = val
                    deductions.append(f"Computed {step.arg} = {val}")

                elif step.op == "DEDUCE":
                    conclusion = await self._execute_deduce(step.arg, all_chunks, model)
                    deductions.append(conclusion)
                    step.result = conclusion

                elif step.op == "OUTPUT":
                    answer = "\n".join(deductions) if deductions else ""
                    step.result = answer

            except Exception as e:
                logger.warning(f"KAG step {step.op}({step.arg}) failed: {e}")

        # Deduplicate
        seen: dict[str, dict] = {}
        for c in all_chunks:
            cid = c.get("id", "")
            if cid and (cid not in seen or c.get("score", 0) > seen[cid].get("score", 0)):
                seen[cid] = c

        ranked = sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        return EngineResult(
            engine="kag",
            chunks=ranked,
            answer=answer,
            confidence=min(1.0, len(ranked) / max(top_k, 1)),
            metadata={
                "steps_executed": len(steps),
                "deductions": deductions,
                "math_vars": math_vars,
            },
        )
