"""Tests for Qdrant indexer component (all Qdrant calls mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rrag_ingestion.core.base import ComponentResult


@pytest.fixture
def indexer():
    from rrag_ingestion.components.indexers.qdrant_indexer import QdrantIndexer
    return QdrantIndexer()


@pytest.fixture
def sample_embeddings_input():
    """Input with embeddings and chunks, mimicking pipeline output."""
    return ComponentResult(data={
        "embeddings": [
            {"id": "chunk-1", "vector": [0.1] * 1536},
            {"id": "chunk-2", "vector": [0.2] * 1536},
            {"id": "chunk-3", "vector": [0.3] * 1536},
        ],
        "chunks": [
            {"id": "chunk-1", "content": "The quick brown fox.", "metadata": {"page": 1}},
            {"id": "chunk-2", "content": "Machine learning basics.", "metadata": {"page": 2}},
            {"id": "chunk-3", "content": "Deep learning overview.", "metadata": {"page": 3}},
        ],
        "document_ids": ["doc-1"],
        "workspace_id": "ws-test",
    })


@pytest.fixture
def default_config():
    return {
        "url": "http://localhost:6333",
        "api_key": "",
        "collection_name": "test_collection",
        "dimension": 1536,
        "distance": "cosine",
        "overwrite": False,
    }


class TestQdrantIndexerMetadata:
    def test_name(self, indexer):
        assert indexer.name == "qdrant_indexer"

    def test_version(self, indexer):
        assert indexer.version == "0.1.0"

    def test_config_schema_has_required_keys(self, indexer):
        schema = indexer.config_schema
        assert "url" in schema
        assert "collection_name" in schema
        assert "dimension" in schema
        assert "distance" in schema


class TestQdrantIndexerInvoke:
    @pytest.mark.asyncio
    async def test_empty_embeddings_returns_error(self, indexer, default_config):
        input_data = ComponentResult(data={"embeddings": []})
        result = await indexer.invoke(input_data, default_config)
        assert result.errors
        assert "No embeddings" in result.errors[0]

    @pytest.mark.asyncio
    async def test_missing_qdrant_returns_import_error(self, indexer, sample_embeddings_input, default_config):
        with patch.dict("sys.modules", {"qdrant_client": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'qdrant_client'")):
                result = await indexer.invoke(sample_embeddings_input, default_config)
                assert result.errors
                assert "qdrant-client not installed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_successful_indexing(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_models = MagicMock()

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch("qdrant_client.models", mock_models):
                result = await indexer.invoke(sample_embeddings_input, default_config)

        assert not result.errors
        assert result.metadata["indexed_count"] == 3
        assert result.metadata["dimensions"] == 1536
        assert result.metadata["collection_name"] == "test_collection"
        assert result.data["collection_name"] == "test_collection"

        # Verify collection creation was called
        mock_client.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_overwrite_deletes_existing_collection(self, indexer, sample_embeddings_input):
        config = {
            "url": "http://localhost:6333",
            "collection_name": "test_collection",
            "dimension": 1536,
            "distance": "cosine",
            "overwrite": True,
        }
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_models = MagicMock()

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch("qdrant_client.models", mock_models):
                result = await indexer.invoke(sample_embeddings_input, config)

        assert not result.errors
        mock_client.delete_collection.assert_called_once_with("test_collection")

    @pytest.mark.asyncio
    async def test_skips_delete_when_not_overwrite(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_models = MagicMock()

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch("qdrant_client.models", mock_models):
                result = await indexer.invoke(sample_embeddings_input, default_config)

        assert not result.errors
        mock_client.delete_collection.assert_not_called()
        # Should not create since it already exists
        mock_client.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_called_with_points(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_models = MagicMock()

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            with patch("qdrant_client.models", mock_models):
                await indexer.invoke(sample_embeddings_input, default_config)

        # Should have called upsert at least once
        mock_client.upsert.assert_called()
        call_args = mock_client.upsert.call_args
        assert call_args.kwargs["collection_name"] == "test_collection"
        points = call_args.kwargs["points"]
        assert len(points) == 3

    @pytest.mark.asyncio
    async def test_distance_metric_mapping(self, indexer, sample_embeddings_input):
        for distance in ["cosine", "euclid", "dot"]:
            config = {
                "url": "http://localhost:6333",
                "collection_name": "test_collection",
                "dimension": 1536,
                "distance": distance,
                "overwrite": True,
            }
            mock_client = MagicMock()
            mock_client.collection_exists.return_value = False
            mock_models = MagicMock()

            with patch("qdrant_client.QdrantClient", return_value=mock_client):
                with patch("qdrant_client.models", mock_models):
                    result = await indexer.invoke(sample_embeddings_input, config)

            assert not result.errors
