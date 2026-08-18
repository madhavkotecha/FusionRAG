from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from rrag_ingestion.components.extractors.base import BaseExtractor
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Entity, Relation, SubGraph

logger = logging.getLogger(__name__)

ENTITY_EXTRACTION_PROMPT = """Given the following text, extract all entities and relationships.

For each entity, output a line:
ENTITY|name|type|description

For each relationship between entities, output a line:
RELATION|source_entity|target_entity|relationship_type|description|keywords

Entity types to look for: {entity_types}

Text:
{text}

Output only ENTITY and RELATION lines, nothing else."""

GLEANING_PROMPT = """The following entities and relationships were already extracted:
{existing}

Are there any entities or relationships that were missed? If so, output additional lines.
If nothing was missed, output NONE.

Text:
{text}"""


@register_component
class LightRAGEntityExtractor(BaseExtractor):
    """LLM-based entity and relation extractor from LightRAG."""

    name = "lightrag.entity_extractor"
    version = "0.1.0"
    description = "LLM-based entity and relationship extraction with gleaning (from LightRAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "entity_types": {
            "type": "array",
            "default": ["Person", "Organization", "Location", "Event", "Concept", "Technology", "Document"],
        },
        "max_gleaning": {"type": "integer", "default": 1, "description": "Number of gleaning iterations"},
        "temperature": {"type": "number", "default": 0.0},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        if not chunks:
            return ComponentResult(data={"subgraph": SubGraph(), **input_data.data}, errors=["No chunks to extract from"])

        model = config.get("llm_model", "gpt-4o-mini")
        entity_types = config.get("entity_types", ["Person", "Organization", "Location", "Event", "Concept"])
        max_gleaning = config.get("max_gleaning", 1)
        temperature = config.get("temperature", 0.0)

        all_entities: dict[str, Entity] = {}
        all_relations: list[Relation] = []
        errors = []

        for ci, chunk in enumerate(chunks):
            chunk_content = chunk.content if hasattr(chunk, "content") else chunk.get("content", "")
            chunk_id = chunk.id if hasattr(chunk, "id") else chunk.get("id", "")
            if not chunk_content:
                continue

            self.report_progress(
                f"Extracting entities from chunk {ci + 1}/{len(chunks)}",
                items_done=ci,
                items_total=len(chunks),
            )

            try:
                entities, relations = await self._extract_from_chunk(
                    chunk_content, chunk_id, model, entity_types, max_gleaning, temperature
                )
                for ent in entities:
                    if ent.name in all_entities:
                        existing = all_entities[ent.name]
                        existing.source_chunks.extend(ent.source_chunks)
                        if ent.description and len(ent.description) > len(existing.description):
                            existing.description = ent.description
                    else:
                        all_entities[ent.name] = ent
                all_relations.extend(relations)
            except Exception as e:
                errors.append(f"Extraction failed for chunk {chunk_id}: {e}")

        subgraph = SubGraph(
            nodes=list(all_entities.values()),
            edges=all_relations,
        )

        return ComponentResult(
            data={**input_data.data, "subgraph": subgraph},
            metadata={
                "entity_count": len(subgraph.nodes),
                "relation_count": len(subgraph.edges),
            },
            errors=errors,
        )

    async def _extract_from_chunk(
        self, text: str, chunk_id: str, model: str, entity_types: list[str],
        max_gleaning: int, temperature: float,
    ) -> tuple[list[Entity], list[Relation]]:
        from rrag_ingestion.services.openai_client import get_openai_client

        client = get_openai_client()

        prompt = ENTITY_EXTRACTION_PROMPT.format(
            entity_types=", ".join(entity_types),
            text=text,
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        raw_output = response.choices[0].message.content or ""
        entities, relations = self._parse_extraction(raw_output, chunk_id)

        # Gleaning: ask for missed entities
        for _ in range(max_gleaning):
            existing_lines = raw_output.strip()
            gleaning_prompt = GLEANING_PROMPT.format(existing=existing_lines, text=text)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": gleaning_prompt}],
                temperature=temperature,
            )
            gleaning_output = response.choices[0].message.content or ""
            if "NONE" in gleaning_output.upper():
                break
            more_entities, more_relations = self._parse_extraction(gleaning_output, chunk_id)
            entities.extend(more_entities)
            relations.extend(more_relations)
            raw_output += "\n" + gleaning_output

        return entities, relations

    def _parse_extraction(self, raw: str, chunk_id: str) -> tuple[list[Entity], list[Relation]]:
        entities = []
        relations = []

        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.startswith("ENTITY|"):
                parts = line.split("|")
                if len(parts) >= 4:
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=parts[1].strip(),
                        entity_type=parts[2].strip(),
                        description=parts[3].strip(),
                        source_chunks=[chunk_id],
                    ))
            elif line.startswith("RELATION|"):
                parts = line.split("|")
                if len(parts) >= 5:
                    keywords = parts[5].strip().split(",") if len(parts) > 5 else []
                    relations.append(Relation(
                        id=str(uuid.uuid4()),
                        source_entity=parts[1].strip(),
                        target_entity=parts[2].strip(),
                        relation_type=parts[3].strip(),
                        description=parts[4].strip(),
                        keywords=[k.strip() for k in keywords],
                        source_chunks=[chunk_id],
                    ))

        return entities, relations
