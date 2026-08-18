"""ADR-0010: Mutual Index for Provenance and Citation Tracking.

Bidirectional links stored in OpenSearch:
  Forward: KG entity/relation ID → list of source chunk IDs
  Reverse: chunk ID → list of KG node/relation IDs

Index name: rrag_mutual_index
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MUTUAL_INDEX = "rrag_mutual_index"

_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "forward_id": {"type": "keyword"},   # KG node/relation ID
            "forward_name": {"type": "keyword"},  # human-readable entity name
            "chunk_ids": {"type": "keyword"},     # list of chunk IDs
            "type": {"type": "keyword"},          # "entity" | "relation"
            "datastore_id": {"type": "keyword"},
        }
    }
}

_REVERSE_INDEX = "rrag_mutual_index_reverse"

_REVERSE_MAPPING = {
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "kg_node_ids": {"type": "keyword"},   # entity/relation IDs
            "datastore_id": {"type": "keyword"},
        }
    }
}


class MutualIndex:
    """Bidirectional KG↔chunk provenance index (ADR-0010)."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._host = host or os.environ.get("RRAG_OPENSEARCH_HOST", "opensearch")
        self._port = port or int(os.environ.get("RRAG_OPENSEARCH_PORT", "9200"))
        self._user = user or os.environ.get("OPENSEARCH_USERNAME", "admin")
        self._password = password or os.environ.get("OPENSEARCH_PASSWORD", "")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from opensearchpy import OpenSearch
            kwargs: dict = {
                "hosts": [{"host": self._host, "port": self._port}],
                "use_ssl": False,
                "verify_certs": False,
                "ssl_show_warn": False,
            }
            if self._password:
                kwargs["http_auth"] = (self._user, self._password)
            self._client = OpenSearch(**kwargs)
        return self._client

    def ensure_indices(self) -> None:
        """Create both indices if they don't exist."""
        client = self._get_client()
        for idx, mapping in [
            (MUTUAL_INDEX, _INDEX_MAPPING),
            (_REVERSE_INDEX, _REVERSE_MAPPING),
        ]:
            try:
                if not client.indices.exists(index=idx):
                    client.indices.create(index=idx, body=mapping)
            except Exception as e:
                logger.warning(f"Could not create index {idx}: {e}")

    # ── Write ─────────────────────────────────────────────────────────────

    def index_entity_chunks(
        self,
        entity_id: str,
        entity_name: str,
        chunk_ids: list[str],
        entity_type: str = "entity",
        datastore_id: str = "",
    ) -> None:
        """Forward link: entity → chunks that sourced it."""
        client = self._get_client()
        doc = {
            "forward_id": entity_id,
            "forward_name": entity_name,
            "chunk_ids": chunk_ids,
            "type": entity_type,
            "datastore_id": datastore_id,
        }
        try:
            client.index(index=MUTUAL_INDEX, id=entity_id, body=doc)
        except Exception as e:
            logger.warning(f"MutualIndex forward write failed for {entity_id}: {e}")

    def index_chunk_entities(
        self,
        chunk_id: str,
        kg_node_ids: list[str],
        datastore_id: str = "",
    ) -> None:
        """Reverse link: chunk → KG nodes extracted from it."""
        client = self._get_client()
        doc = {
            "chunk_id": chunk_id,
            "kg_node_ids": kg_node_ids,
            "datastore_id": datastore_id,
        }
        try:
            client.index(index=_REVERSE_INDEX, id=chunk_id, body=doc)
        except Exception as e:
            logger.warning(f"MutualIndex reverse write failed for {chunk_id}: {e}")

    def update_entity_chunks(self, entity_id: str, new_chunk_ids: list[str]) -> None:
        """Append new chunk IDs to an existing entity's forward links."""
        client = self._get_client()
        try:
            existing = client.get(index=MUTUAL_INDEX, id=entity_id, ignore=[404])
            if existing.get("found"):
                current = existing["_source"].get("chunk_ids", [])
                merged = list(dict.fromkeys(current + new_chunk_ids))
                client.update(
                    index=MUTUAL_INDEX,
                    id=entity_id,
                    body={"doc": {"chunk_ids": merged}},
                )
            else:
                logger.debug(f"Entity {entity_id} not in mutual index; skipping update")
        except Exception as e:
            logger.warning(f"MutualIndex update failed for {entity_id}: {e}")

    # ── Read ──────────────────────────────────────────────────────────────

    def get_chunks_for_entity(self, entity_id: str) -> list[str]:
        """Forward lookup: entity ID → source chunk IDs."""
        client = self._get_client()
        try:
            resp = client.get(index=MUTUAL_INDEX, id=entity_id, ignore=[404])
            if resp.get("found"):
                return resp["_source"].get("chunk_ids", [])
        except Exception as e:
            logger.warning(f"MutualIndex forward lookup failed: {e}")
        return []

    def get_entities_for_chunk(self, chunk_id: str) -> list[str]:
        """Reverse lookup: chunk ID → KG node IDs."""
        client = self._get_client()
        try:
            resp = client.get(index=_REVERSE_INDEX, id=chunk_id, ignore=[404])
            if resp.get("found"):
                return resp["_source"].get("kg_node_ids", [])
        except Exception as e:
            logger.warning(f"MutualIndex reverse lookup failed: {e}")
        return []

    def get_provenance_chain(self, entity_id: str) -> dict:
        """Full provenance chain: entity → chunks → document info."""
        chunk_ids = self.get_chunks_for_entity(entity_id)
        return {"entity_id": entity_id, "source_chunk_ids": chunk_ids, "chunk_count": len(chunk_ids)}

    def search_entities_by_name(self, name: str, datastore_id: str = "") -> list[dict]:
        """Find mutual index entries by entity name (for citation linking)."""
        client = self._get_client()
        must: list[dict] = [{"term": {"forward_name": name}}]
        if datastore_id:
            must.append({"term": {"datastore_id": datastore_id}})
        try:
            resp = client.search(
                index=MUTUAL_INDEX,
                body={"query": {"bool": {"must": must}}, "size": 10},
            )
            results = []
            for hit in resp.get("hits", {}).get("hits", []):
                src = hit["_source"]
                results.append({
                    "entity_id": src.get("forward_id"),
                    "entity_name": src.get("forward_name"),
                    "chunk_ids": src.get("chunk_ids", []),
                    "type": src.get("type"),
                })
            return results
        except Exception as e:
            logger.warning(f"MutualIndex name search failed: {e}")
            return []
