from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import numpy as np

from rrag_ingestion.components.indexers.base import BaseIndexer
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


@register_component
class QdrantIndexer(BaseIndexer):
    """Qdrant vector indexer with HNSW for dedicated vector similarity search."""

    name = "qdrant_indexer"
    version = "0.1.0"
    description = "Index embeddings into Qdrant for fast vector similarity search"
    config_schema = {
        "url": {"type": "string", "default": "http://localhost:6333"},
        "api_key": {"type": "string", "default": ""},
        "collection_name": {"type": "string", "default": "rrag_vectors"},
        "dimension": {"type": "integer", "default": 1536},
        "distance": {"type": "string", "default": "cosine", "enum": ["cosine", "euclid", "dot"]},
        "overwrite": {"type": "boolean", "default": False},
        "hnsw_m": {"type": "integer", "default": 16},
        "hnsw_ef_construct": {"type": "integer", "default": 128},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        embeddings = input_data.data.get("embeddings", [])
        if not embeddings:
            return ComponentResult(data=input_data.data, errors=["No embeddings to index"])

        url = config.get("url") or os.environ.get("RRAG_QDRANT_URL", "http://localhost:6333")
        api_key = config.get("api_key") or os.environ.get("RRAG_QDRANT_API_KEY") or None
        # Per-datastore collection: use datastore_id to isolate vectors
        datastore_id = input_data.data.get("datastore_id", "")
        default_collection = f"rrag_ds_{datastore_id}" if datastore_id else "rrag_vectors"
        collection_name = config.get("collection_name", default_collection)
        dimension = config.get("dimension", 1536)
        distance = config.get("distance", "cosine")
        overwrite = config.get("overwrite", False)
        hnsw_m = config.get("hnsw_m", 16)
        hnsw_ef_construct = config.get("hnsw_ef_construct", 128)

        try:
            from qdrant_client import QdrantClient, models

            client = QdrantClient(
                url=url,
                api_key=api_key,
                timeout=60,
                check_compatibility=False,
            )

            # Map distance string to Qdrant enum
            distance_map = {
                "cosine": models.Distance.COSINE,
                "euclid": models.Distance.EUCLID,
                "dot": models.Distance.DOT,
            }
            qdrant_distance = distance_map.get(distance, models.Distance.COSINE)

            # Create or recreate collection
            if overwrite and client.collection_exists(collection_name):
                client.delete_collection(collection_name)

            if not client.collection_exists(collection_name):
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=dimension,
                        distance=qdrant_distance,
                    ),
                    hnsw_config=models.HnswConfigDiff(
                        m=hnsw_m,
                        ef_construct=hnsw_ef_construct,
                    ),
                )
                logger.info(f"Created Qdrant collection: {collection_name} ({dimension}D, {distance})")

            # Build points
            chunks = input_data.data.get("chunks", [])
            workspace_id = input_data.data.get("workspace_id", "")
            document_ids = input_data.data.get("document_ids", [])
            first_doc_id = document_ids[0] if document_ids else ""

            points = []
            for i, emb in enumerate(embeddings):
                vector = emb.vector if hasattr(emb, "vector") else emb.get("vector")
                eid = emb.id if hasattr(emb, "id") else emb.get("id", str(i))

                # Find corresponding chunk content
                content = ""
                chunk_metadata: dict[str, Any] = {}
                doc_id = first_doc_id
                for c in chunks:
                    cid = c.id if hasattr(c, "id") else c.get("id", "")
                    if cid == eid:
                        content = c.content if hasattr(c, "content") else c.get("content", "")
                        chunk_metadata = c.metadata if hasattr(c, "metadata") else c.get("metadata", {})
                        doc_id = chunk_metadata.get("document_id", first_doc_id)
                        break

                # Use UUID for Qdrant point ID
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, eid))

                points.append(models.PointStruct(
                    id=point_id,
                    vector=np.array(vector, dtype=np.float32).tolist(),
                    payload={
                        "content": content,
                        "chunk_id": eid,
                        "document_id": doc_id,
                        "workspace_id": workspace_id,
                        "metadata": chunk_metadata,
                    },
                ))

            # Batch upsert
            total_indexed = 0
            total_batches = (len(points) + BATCH_SIZE - 1) // BATCH_SIZE
            for batch_idx, batch_start in enumerate(range(0, len(points), BATCH_SIZE)):
                batch = points[batch_start : batch_start + BATCH_SIZE]
                self.report_progress(
                    f"Indexing to Qdrant batch {batch_idx + 1}/{total_batches} ({min(batch_start + BATCH_SIZE, len(points))}/{len(points)} vectors)",
                    items_done=batch_start,
                    items_total=len(points),
                )
                client.upsert(collection_name=collection_name, points=batch)
                total_indexed += len(batch)

            logger.info(
                f"Indexed {total_indexed}/{len(points)} vectors to Qdrant collection '{collection_name}'"
            )

            return ComponentResult(
                data={
                    **input_data.data,
                    "collection_name": collection_name,
                    "qdrant_url": url,
                },
                metadata={
                    "indexed_count": total_indexed,
                    "dimensions": dimension,
                    "collection_name": collection_name,
                    "url": url,
                },
            )

        except ImportError:
            return ComponentResult(
                data=input_data.data,
                errors=["qdrant-client not installed. Install with: pip install qdrant-client"],
            )
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"Qdrant indexing failed: {e}"])
