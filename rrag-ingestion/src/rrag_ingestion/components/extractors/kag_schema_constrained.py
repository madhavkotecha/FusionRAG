from __future__ import annotations

import json
import logging
import uuid

from rrag_ingestion.components.extractors.base import BaseExtractor
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Entity, Relation, SubGraph

logger = logging.getLogger(__name__)

SCHEMA_EXTRACTION_PROMPT = """Given the following schema and text, extract entities and relationships that conform to the schema.

Schema:
{schema}

For each entity found, output:
ENTITY|name|type|property1=value1|property2=value2

For each relationship found, output:
RELATION|source|target|relation_type|property1=value1

Text:
{text}"""


@register_component
class KAGSchemaConstrainedExtractor(BaseExtractor):
    """Schema-constrained extraction inspired by KAG's KG_cs layer."""

    name = "kag.schema_constrained_extractor"
    version = "0.1.0"
    description = "Schema-constrained entity/relation extraction with domain ontology (from KAG)"
    config_schema = {
        "llm_model": {"type": "string", "default": "gpt-4o-mini"},
        "schema": {
            "type": "object",
            "description": "Domain ontology schema defining entity types and relation types",
            "default": {
                "entity_types": {
                    "Person": ["name", "role", "affiliation"],
                    "Organization": ["name", "type", "location"],
                    "Technology": ["name", "category", "version"],
                },
                "relation_types": ["works_at", "develops", "uses", "part_of", "located_in"],
            },
        },
        "temperature": {"type": "number", "default": 0.0},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        chunks = input_data.data.get("chunks", [])
        model = config.get("llm_model", "gpt-4o-mini")
        schema = config.get("schema", self.config_schema["schema"]["default"])
        temperature = config.get("temperature", 0.0)

        all_entities: dict[str, Entity] = {}
        all_relations: list[Relation] = []
        errors = []

        schema_text = json.dumps(schema, indent=2)

        for ci, chunk in enumerate(chunks):
            content = chunk.content if hasattr(chunk, "content") else chunk.get("content", "")
            chunk_id = chunk.id if hasattr(chunk, "id") else chunk.get("id", "")
            if not content:
                continue

            self.report_progress(f"Schema extraction chunk {ci + 1}/{len(chunks)}", items_done=ci, items_total=len(chunks))

            try:
                from rrag_ingestion.services.openai_client import get_openai_client
                client = get_openai_client()

                prompt = SCHEMA_EXTRACTION_PROMPT.format(schema=schema_text, text=content)
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                raw = response.choices[0].message.content or ""

                for line in raw.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("ENTITY|"):
                        parts = line.split("|")
                        if len(parts) >= 3:
                            name = parts[1].strip()
                            etype = parts[2].strip()
                            props = {}
                            for p in parts[3:]:
                                if "=" in p:
                                    k, v = p.split("=", 1)
                                    props[k.strip()] = v.strip()
                            if name not in all_entities:
                                all_entities[name] = Entity(
                                    id=str(uuid.uuid4()),
                                    name=name,
                                    entity_type=etype,
                                    properties=props,
                                    source_chunks=[chunk_id],
                                )
                    elif line.startswith("RELATION|"):
                        parts = line.split("|")
                        if len(parts) >= 4:
                            props = {}
                            for p in parts[4:]:
                                if "=" in p:
                                    k, v = p.split("=", 1)
                                    props[k.strip()] = v.strip()
                            all_relations.append(Relation(
                                id=str(uuid.uuid4()),
                                source_entity=parts[1].strip(),
                                target_entity=parts[2].strip(),
                                relation_type=parts[3].strip(),
                                source_chunks=[chunk_id],
                            ))
            except Exception as e:
                errors.append(f"Schema extraction failed for chunk {chunk_id}: {e}")

        subgraph = SubGraph(nodes=list(all_entities.values()), edges=all_relations)

        return ComponentResult(
            data={**input_data.data, "subgraph": subgraph},
            metadata={"entity_count": len(all_entities), "relation_count": len(all_relations)},
            errors=errors,
        )
