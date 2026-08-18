"""Tests for OpenSearch retriever component (all calls mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rrag_ingestion.core.base import ComponentResult


def _make_search_response(hits: list[dict]) -> dict:
    """Build a mock OpenSearch search response."""
    return {
        "hits": {
            "total": {"value": len(hits)},
            "hits": [
                {
                    "_id": h["id"],
                    "_score": h.get("score", 1.0),
                    "_source": {
                        "chunk_id": h["id"],
                        "content": h.get("content", ""),
                        "document_id": h.get("document_id", "doc-1"),
                        "workspace_id": h.get("workspace_id", "ws-test"),
                        "metadata": h.get("metadata", {}),
                    },
                }
                for h in hits
            ],
        },
    }


@pytest.fixture
def retriever():
    from rrag_ingestion.components.retrievers.opensearch_retriever import OpenSearchRetriever
    return OpenSearchRetriever()


@pytest.fixture
def default_config():
    return {
        "host": "localhost",
        "port": 9200,
        "index_name": "test_index",
        "top_k": 5,
        "search_mode": "hybrid",
        "embedding_model": "openai",
    }


@pytest.fixture
def query_input():
    return ComponentResult(data={"query": "What is machine learning?"})


class TestOpenSearchRetrieverMetadata:
    def test_name(self, retriever):
        assert retriever.name == "opensearch_retriever"

    def test_search_modes(self, retriever):
        modes = retriever.config_schema["search_mode"]["enum"]
        assert "knn" in modes
        assert "bm25" in modes
        assert "hybrid" in modes


class TestOpenSearchRetrieverInvoke:
    @pytest.mark.asyncio
    async def test_no_query_returns_error(self, retriever, default_config):
        input_data = ComponentResult(data={})
        result = await retriever.invoke(input_data, default_config)
        assert result.errors
        assert "No query" in result.errors[0]

    @pytest.mark.asyncio
    async def test_knn_search(self, retriever, query_input):
        config = {
            "host": "localhost",
            "port": 9200,
            "index_name": "test_index",
            "top_k": 3,
            "search_mode": "knn",
            "embedding_model": "openai",
        }

        mock_client = MagicMock()
        mock_client.search.return_value = _make_search_response([
            {"id": "c1", "content": "ML basics", "score": 0.95},
            {"id": "c2", "content": "Deep learning", "score": 0.85},
        ])

        mock_embed = [0.1] * 1536

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(query_input, config)

        assert not result.errors
        assert len(result.data["retrieved"]) == 2
        assert result.data["retrieved"][0].id == "c1"
        assert result.metadata["search_mode"] == "knn"

    @pytest.mark.asyncio
    async def test_bm25_search(self, retriever, query_input):
        config = {
            "host": "localhost",
            "port": 9200,
            "index_name": "test_index",
            "top_k": 3,
            "search_mode": "bm25",
            "embedding_model": "openai",
        }

        mock_client = MagicMock()
        mock_client.search.return_value = _make_search_response([
            {"id": "c3", "content": "Text about ML", "score": 5.2},
        ])

        mock_embed = [0.1] * 1536

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(query_input, config)

        assert not result.errors
        assert len(result.data["retrieved"]) == 1
        assert result.metadata["search_mode"] == "bm25"

    @pytest.mark.asyncio
    async def test_hybrid_search_deduplicates(self, retriever, query_input):
        config = {
            "host": "localhost",
            "port": 9200,
            "index_name": "test_index",
            "top_k": 5,
            "search_mode": "hybrid",
            "embedding_model": "openai",
        }

        mock_client = MagicMock()
        # kNN and BM25 return overlapping results
        knn_response = _make_search_response([
            {"id": "c1", "content": "Shared result", "score": 0.9},
            {"id": "c2", "content": "KNN only", "score": 0.8},
        ])
        bm25_response = _make_search_response([
            {"id": "c1", "content": "Shared result", "score": 5.0},
            {"id": "c3", "content": "BM25 only", "score": 4.0},
        ])
        mock_client.search.side_effect = [knn_response, bm25_response]

        mock_embed = [0.1] * 1536

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(query_input, config)

        assert not result.errors
        retrieved = result.data["retrieved"]
        ids = [r.id for r in retrieved]
        # All unique
        assert len(ids) == len(set(ids))
        # c1 should be first (appears in both lists, highest RRF score)
        assert ids[0] == "c1"
        assert "c2" in ids
        assert "c3" in ids


class TestRRFFusion:
    def test_fuses_two_lists(self):
        from rrag_ingestion.components.retrievers.opensearch_retriever import _rrf_fuse
        from rrag_ingestion.models.document import RetrievalResult

        knn = [
            RetrievalResult(id="a", content="A", score=0.9, metadata={}),
            RetrievalResult(id="b", content="B", score=0.8, metadata={}),
        ]
        bm25 = [
            RetrievalResult(id="a", content="A", score=5.0, metadata={}),
            RetrievalResult(id="c", content="C", score=4.0, metadata={}),
        ]

        fused = _rrf_fuse(knn, bm25, top_k=3, rrf_k=60)
        ids = [r.id for r in fused]

        # 'a' appears in both, should have highest score
        assert ids[0] == "a"
        assert len(fused) == 3
        # All unique
        assert len(set(ids)) == 3

    def test_respects_top_k(self):
        from rrag_ingestion.components.retrievers.opensearch_retriever import _rrf_fuse
        from rrag_ingestion.models.document import RetrievalResult

        knn = [RetrievalResult(id=f"k{i}", content=f"K{i}", score=1.0 - i * 0.1, metadata={}) for i in range(10)]
        bm25 = [RetrievalResult(id=f"b{i}", content=f"B{i}", score=5.0 - i * 0.5, metadata={}) for i in range(10)]

        fused = _rrf_fuse(knn, bm25, top_k=5, rrf_k=60)
        assert len(fused) == 5

    def test_empty_lists(self):
        from rrag_ingestion.components.retrievers.opensearch_retriever import _rrf_fuse

        fused = _rrf_fuse([], [], top_k=5, rrf_k=60)
        assert fused == []

    def test_single_list_empty(self):
        from rrag_ingestion.components.retrievers.opensearch_retriever import _rrf_fuse
        from rrag_ingestion.models.document import RetrievalResult

        knn = [RetrievalResult(id="a", content="A", score=0.9, metadata={})]
        fused = _rrf_fuse(knn, [], top_k=5, rrf_k=60)
        assert len(fused) == 1
        assert fused[0].id == "a"
