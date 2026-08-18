from __future__ import annotations

import logging
import uuid

from rrag_ingestion.components.extractors.base import BaseExtractor
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Entity, Relation, SubGraph

logger = logging.getLogger(__name__)

OPENIE_PROMPT = """Extract all factual triples (subject, predicate, object) from the text below.
Output each triple on a separate line in this format:
TRIPLE|subject|predicate|object

Be comprehensive. Extract every factual statement as a triple.

Text:
{text}"""


@register_component
class KAGSchemaFreeExtractor(BaseExtractor):
    """Schema-free OpenIE extraction inspired by KAG's KG_fr layer."""

    name = "kag.schema_free_extractor"
    version = "0.1.0"
    description = "Schema-free Open Information Extraction (OpenIE) for knowledge graph construction (from KAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "temperature": {"type": "number", "default": 0.0},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        model = config.get("llm_model", "gpt-4o-mini")
        temperature = config.get("temperature", 0.0)
        existing_subgraph = input_data.data.get("subgraph")

        all_entities: dict[str, Entity] = {}
        all_relations: list[Relation] = []
        errors = []

        # Preserve existing subgraph if present
        if existing_subgraph:
            for node in (existing_subgraph.nodes if hasattr(existing_subgraph, "nodes") else []):
                all_entities[node.name] = node

        for ci, chunk in enumerate(chunks):
            content = chunk.content if hasattr(chunk, "content") else chunk.get("content", "")
            chunk_id = chunk.id if hasattr(chunk, "id") else chunk.get("id", "")
            if not content:
                continue

            self.report_progress(f"Extracting triples from chunk {ci + 1}/{len(chunks)}", items_done=ci, items_total=len(chunks))

            try:
                entities, relations = await self._extract_triples(content, chunk_id, model, temperature)
                for ent in entities:
                    if ent.name not in all_entities:
                        all_entities[ent.name] = ent
                    else:
                        all_entities[ent.name].source_chunks.extend(ent.source_chunks)
                all_relations.extend(relations)
            except Exception as e:
                errors.append(f"OpenIE extraction failed for chunk {chunk_id}: {e}")

        subgraph = SubGraph(
            nodes=list(all_entities.values()),
            edges=all_relations,
        )

        return ComponentResult(
            data={**input_data.data, "subgraph": subgraph},
            metadata={"triple_count": len(all_relations), "entity_count": len(all_entities)},
            errors=errors,
        )

    async def _extract_triples(
        self, text: str, chunk_id: str, model: str, temperature: float
    ) -> tuple[list[Entity], list[Relation]]:
        from rrag_ingestion.services.openai_client import get_openai_client

        client = get_openai_client()
        prompt = OPENIE_PROMPT.format(text=text)

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        raw = response.choices[0].message.content or ""
        entities_map: dict[str, Entity] = {}
        relations = []

        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.startswith("TRIPLE|"):
                parts = line.split("|")
                if len(parts) >= 4:
                    subj = parts[1].strip()
                    pred = parts[2].strip()
                    obj = parts[3].strip()

                    for name in [subj, obj]:
                        if name not in entities_map:
                            entities_map[name] = Entity(
                                id=str(uuid.uuid4()),
                                name=name,
                                entity_type="Thing",
                                source_chunks=[chunk_id],
                            )

                    relations.append(Relation(
                        id=str(uuid.uuid4()),
                        source_entity=subj,
                        target_entity=obj,
                        relation_type=pred,
                        description=f"{subj} {pred} {obj}",
                        source_chunks=[chunk_id],
                    ))

        return list(entities_map.values()), relations
