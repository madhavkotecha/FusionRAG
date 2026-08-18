from __future__ import annotations

import json
import logging
import os
from typing import Any

import numpy as np

from rrag_ingestion.components.indexers.base import BaseIndexer
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class FAISSIndexer(BaseIndexer):
    """FAISS vector index backend extracted from UltraRAG."""

    name = "faiss_indexer"
    version = "0.1.0"
    description = "FAISS flat index for vector similarity search (from UltraRAG)"
    config_schema = {
        "index_path": {"type": "string", "default": "/data/documents/faiss_index"},
        "overwrite": {"type": "boolean", "default": False},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        embeddings = input_data.data.get("embeddings", [])
        if not embeddings:
            return ComponentResult(data=input_data.data, errors=["No embeddings to index"])

        index_path = config.get("index_path", "/data/documents/faiss_index")

        try:
            import faiss

            vectors = np.array([e.vector if hasattr(e, "vector") else e.get("vector") for e in embeddings], dtype=np.float32)
            ids = np.arange(len(vectors), dtype=np.int64)

            dim = vectors.shape[1]
            index = faiss.IndexFlatIP(dim)
            id_index = faiss.IndexIDMap(index)
            id_index.add_with_ids(vectors, ids)

            os.makedirs(os.path.dirname(index_path) if os.path.dirname(index_path) else ".", exist_ok=True)
            faiss.write_index(id_index, index_path)

            # Build and persist ID-to-content mapping alongside the index
            id_map = {}
            chunks = input_data.data.get("chunks", [])
            chunk_store = []
            for i, emb in enumerate(embeddings):
                eid = emb.id if hasattr(emb, "id") else emb.get("id", str(i))
                id_map[i] = eid

                # Find corresponding chunk content
                content = ""
                metadata = {}
                for c in chunks:
                    cid = c.id if hasattr(c, "id") else c.get("id", "")
                    if cid == eid:
                        content = c.content if hasattr(c, "content") else c.get("content", "")
                        metadata = c.metadata if hasattr(c, "metadata") else c.get("metadata", {})
                        break

                chunk_store.append({
                    "idx": i,
                    "id": eid,
                    "content": content,
                    "metadata": metadata,
                })

            # Save chunk store alongside FAISS index for retrieval
            chunks_path = index_path + ".chunks.json"
            with open(chunks_path, "w") as f:
                json.dump(chunk_store, f)

            logger.info(f"Indexed {len(vectors)} vectors ({dim}D) to {index_path}, chunks saved to {chunks_path}")

            return ComponentResult(
                data={**input_data.data, "index_path": index_path, "index_id_map": id_map},
                metadata={"indexed_count": len(vectors), "dimensions": dim, "index_path": index_path},
            )

        except ImportError:
            return ComponentResult(data=input_data.data, errors=["faiss-cpu not installed. Install with: pip install faiss-cpu"])
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"FAISS indexing failed: {e}"])
