"""Tests for Qdrant retriever component (all calls mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rrag_ingestion.core.base import ComponentResult


@pytest.fixture
def retriever():
    from rrag_ingestion.components.retrievers.qdrant_retriever import QdrantRetriever
    return QdrantRetriever()


@pytest.fixture
def default_config():
    return {
        "url": "http://localhost:6333",
        "api_key": "",
        "collection_name": "test_collection",
        "top_k": 5,
        "embedding_model": "openai",
    }


@pytest.fixture
def query_input():
    return ComponentResult(data={"query": "What is machine learning?"})


def _make_scored_point(point_id, content, score, chunk_id=None, doc_id="doc-1"):
    """Build a mock Qdrant ScoredPoint."""
    point = MagicMock()
    point.id = point_id
    point.score = score
    point.payload = {
        "content": content,
        "chunk_id": chunk_id or str(point_id),
        "document_id": doc_id,
        "workspace_id": "ws-test",
        "metadata": {},
    }
    return point


class TestQdrantRetrieverMetadata:
    def test_name(self, retriever):
        assert retriever.name == "qdrant_retriever"

    def test_config_schema(self, retriever):
        assert "url" in retriever.config_schema
        assert "collection_name" in retriever.config_schema
        assert "top_k" in retriever.config_schema


class TestQdrantRetrieverInvoke:
    @pytest.mark.asyncio
    async def test_no_query_returns_error(self, retriever, default_config):
        input_data = ComponentResult(data={})
        result = await retriever.invoke(input_data, default_config)
        assert result.errors
        assert "No query" in result.errors[0]

    @pytest.mark.asyncio
    async def test_successful_search(self, retriever, query_input, default_config):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.points = [
            _make_scored_point("p1", "ML basics", 0.95, chunk_id="c1"),
            _make_scored_point("p2", "Deep learning", 0.85, chunk_id="c2"),
        ]
        mock_client.query_points.return_value = mock_result

        mock_embed = [0.1] * 1536

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(query_input, default_config)

        assert not result.errors
        assert len(result.data["retrieved"]) == 2
        assert result.data["retrieved"][0].id == "c1"
        assert result.data["retrieved"][0].score == 0.95
        assert result.metadata["search_mode"] == "vector"

    @pytest.mark.asyncio
    async def test_empty_results(self, retriever, query_input, default_config):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.points = []
        mock_client.query_points.return_value = mock_result

        mock_embed = [0.1] * 1536

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(query_input, default_config)

        assert not result.errors
        assert len(result.data["retrieved"]) == 0

    @pytest.mark.asyncio
    async def test_deduplicates_across_subqueries(self, retriever, default_config):
        input_data = ComponentResult(data={
            "query": "main query",
            "subqueries": ["sub query 1", "sub query 2"],
        })

        mock_client = MagicMock()
        # Both subqueries return overlapping results
        mock_result1 = MagicMock()
        mock_result1.points = [
            _make_scored_point("p1", "Shared result", 0.9, chunk_id="c1"),
            _make_scored_point("p2", "Query 1 only", 0.8, chunk_id="c2"),
        ]
        mock_result2 = MagicMock()
        mock_result2.points = [
            _make_scored_point("p1", "Shared result", 0.85, chunk_id="c1"),
            _make_scored_point("p3", "Query 2 only", 0.7, chunk_id="c3"),
        ]
        mock_client.query_points.side_effect = [mock_result1, mock_result2]

        mock_embed = [0.1] * 1536

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(input_data, default_config)

        assert not result.errors
        retrieved = result.data["retrieved"]
        ids = [r.id for r in retrieved]
        # All unique
        assert len(ids) == len(set(ids))
        # c1 should be first (highest score)
        assert ids[0] == "c1"
        assert "c2" in ids
        assert "c3" in ids

    @pytest.mark.asyncio
    async def test_score_threshold(self, retriever, query_input):
        config = {
            "url": "http://localhost:6333",
            "collection_name": "test_collection",
            "top_k": 10,
            "score_threshold": 0.5,
            "embedding_model": "openai",
        }

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.points = [
            _make_scored_point("p1", "High score", 0.9, chunk_id="c1"),
        ]
        mock_client.query_points.return_value = mock_result

        mock_embed = [0.1] * 1536

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch.object(retriever, "_embed_query", new_callable=AsyncMock, return_value=mock_embed):
                result = await retriever.invoke(query_input, config)

        assert not result.errors
        # Verify score_threshold was passed to query_points
        call_kwargs = mock_client.query_points.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.5
