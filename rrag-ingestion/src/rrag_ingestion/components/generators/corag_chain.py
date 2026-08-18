from __future__ import annotations

import logging

from rrag_ingestion.components.generators.base import BaseGenerator
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class CoRAGChainSynthesizer(BaseGenerator):
    """Chain-of-retrieval answer synthesis from CoRAG."""

    name = "corag.chain_synthesizer"
    version = "0.1.0"
    description = "Multi-hop chain-of-retrieval answer synthesis with intermediate reasoning (from CoRAG)"
    config_schema = {
        "model": {"type": "string", "default": "gpt-4o-mini"},
        "intermediate_temperature": {"type": "number", "default": 0.0},
        "final_temperature": {"type": "number", "default": 0.0},
        "max_tokens": {"type": "integer", "default": 2048},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        query = input_data.data.get("query", "")
        subqueries = input_data.data.get("subqueries", [])
        retrieved = input_data.data.get("retrieved", [])

        if not query:
            return ComponentResult(data=input_data.data, errors=["No query for synthesis"])

        model = config.get("model", "gpt-4o-mini")
        final_temp = config.get("final_temperature", 0.0)
        intermediate_temp = config.get("intermediate_temperature", 0.0)
        max_tokens = config.get("max_tokens", 2048)

        try:
            from rrag_ingestion.services.openai_client import get_openai_client
            client = get_openai_client()

            # Generate intermediate answers for each subquery
            subanswers = input_data.data.get("subanswers", [])
            if subqueries and not subanswers:
                for sq in subqueries:
                    context = "\n".join(
                        doc.content if hasattr(doc, "content") else doc.get("content", "")
                        for doc in retrieved[:5]
                    )
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{
                            "role": "user",
                            "content": f"Given the following documents, answer the query concisely.\n\nDocuments:\n{context}\n\nQuery: {sq}\n\nAnswer:",
                        }],
                        temperature=intermediate_temp,
                        max_tokens=512,
                    )
                    subanswers.append(response.choices[0].message.content or "")

            # Final synthesis
            chain_context = ""
            for i, (sq, sa) in enumerate(zip(subqueries, subanswers)):
                chain_context += f"Step {i + 1}:\n  Question: {sq}\n  Answer: {sa}\n\n"

            doc_context = "\n".join(
                doc.content if hasattr(doc, "content") else doc.get("content", "")
                for doc in retrieved[:10]
            )

            final_prompt = (
                f"Based on the following intermediate reasoning steps and documents, "
                f"provide a comprehensive answer to the main question.\n\n"
                f"Intermediate Steps:\n{chain_context}\n"
                f"Documents:\n{doc_context}\n\n"
                f"Main Question: {query}\n\nFinal Answer:"
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": final_prompt}],
                temperature=final_temp,
                max_tokens=max_tokens,
            )

            answer = response.choices[0].message.content or ""

            return ComponentResult(
                data={
                    **input_data.data,
                    "answer": answer,
                    "subanswers": subanswers,
                    "chain_steps": list(zip(subqueries, subanswers)),
                },
                metadata={
                    "model": model,
                    "chain_length": len(subqueries),
                },
            )

        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Chain synthesis failed: {e}"])
