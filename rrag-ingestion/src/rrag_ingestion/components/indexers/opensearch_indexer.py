from __future__ import annotations

import logging
from typing import Any

import numpy as np

from rrag_ingestion.components.indexers.base import BaseIndexer
from rrag_ingestion.core.base import ComponentResult, register_component

logger = logging.getLogger(__name__)


@register_component
class OpenSearchIndexer(BaseIndexer):
    """OpenSearch vector + text indexer with kNN (HNSW) and BM25 support."""

    name = "opensearch_indexer"
    version = "0.1.0"
    description = "Index embeddings and text into OpenSearch for hybrid kNN + BM25 search"
    config_schema = {
        "host": {"type": "string", "default": "localhost"},
        "port": {"type": "integer", "default": 9200},
        "index_name": {"type": "string", "default": "rrag_vectors"},
        "dimension": {"type": "integer", "default": 1536},
        "use_ssl": {"type": "boolean", "default": False},
        "overwrite": {"type": "boolean", "default": False},
        "hnsw_m": {"type": "integer", "default": 16},
        "hnsw_ef_construction": {"type": "integer", "default": 128},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        embeddings = input_data.data.get("embeddings", [])
        if not embeddings:
            return ComponentResult(data=input_data.data, errors=["No embeddings to index"])

        host = config.get("host", "localhost")
        port = config.get("port", 9200)
        # Per-datastore index: use datastore_id to isolate vectors
        datastore_id = input_data.data.get("datastore_id", "")
        default_index = f"rrag_ds_{datastore_id}" if datastore_id else "rrag_vectors"
        index_name = config.get("index_name", default_index)
        dimension = config.get("dimension", 1536)
        use_ssl = config.get("use_ssl", False)
        overwrite = config.get("overwrite", False)
        hnsw_m = config.get("hnsw_m", 16)
        hnsw_ef_construction = config.get("hnsw_ef_construction", 128)

        try:
            from opensearchpy import OpenSearch, helpers

            client = OpenSearch(
                hosts=[{"host": host, "port": port}],
                use_ssl=use_ssl,
                verify_certs=False,
                ssl_show_warn=False,
            )

            # Create or recreate index
            if overwrite and client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)

            if not client.indices.exists(index=index_name):
                mapping = {
                    "settings": {
                        "index": {
                            "knn": True,
                            "knn.algo_param.ef_search": 64,
                        },
                    },
                    "mappings": {
                        "properties": {
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": dimension,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "nmslib",
                                    "parameters": {
                                        "m": hnsw_m,
                                        "ef_construction": hnsw_ef_construction,
                                    },
                                },
                            },
                            "content": {"type": "text", "analyzer": "standard"},
                            "chunk_id": {"type": "keyword"},
                            "document_id": {"type": "keyword"},
                            "workspace_id": {"type": "keyword"},
                            "metadata": {"type": "object", "enabled": True},
                        }
                    },
                }
                client.indices.create(index=index_name, body=mapping)
                logger.info(f"Created OpenSearch index: {index_name} ({dimension}D)")

            # Build bulk actions
            chunks = input_data.data.get("chunks", [])
            workspace_id = input_data.data.get("workspace_id", "")
            document_ids = input_data.data.get("document_ids", [])
            first_doc_id = document_ids[0] if document_ids else ""

            actions = []
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

                actions.append({
                    "_index": index_name,
                    "_id": eid,
                    "_source": {
                        "embedding": np.array(vector, dtype=np.float32).tolist(),
                        "content": content,
                        "chunk_id": eid,
                        "document_id": doc_id,
                        "workspace_id": workspace_id,
                        "metadata": chunk_metadata,
                    },
                })

            # Bulk index
            self.report_progress(
                f"Bulk indexing {len(actions)} vectors to OpenSearch",
                items_done=0,
                items_total=len(actions),
            )
            success_count, errors = helpers.bulk(client, actions, raise_on_error=False)
            if errors:
                logger.warning(f"OpenSearch bulk indexing had {len(errors)} errors")

            logger.info(
                f"Indexed {success_count}/{len(actions)} vectors to OpenSearch index '{index_name}'"
            )

            return ComponentResult(
                data={
                    **input_data.data,
                    "index_name": index_name,
                    "opensearch_host": host,
                    "opensearch_port": port,
                },
                metadata={
                    "indexed_count": success_count,
                    "dimensions": dimension,
                    "index_name": index_name,
                    "host": host,
                    "port": port,
                },
            )

        except ImportError:
            return ComponentResult(
                data=input_data.data,
                errors=["opensearch-py not installed. Install with: pip install opensearch-py"],
            )
        except Exception as e:
            return ComponentResult(data=input_data.data, errors=[f"OpenSearch indexing failed: {e}"])
