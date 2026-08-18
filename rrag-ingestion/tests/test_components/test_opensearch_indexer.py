"""Tests for OpenSearch indexer component (all OpenSearch calls mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rrag_ingestion.core.base import ComponentResult


@pytest.fixture
def indexer():
    from rrag_ingestion.components.indexers.opensearch_indexer import OpenSearchIndexer
    return OpenSearchIndexer()


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
        "host": "localhost",
        "port": 9200,
        "index_name": "test_index",
        "dimension": 1536,
        "overwrite": False,
    }


class TestOpenSearchIndexerMetadata:
    def test_name(self, indexer):
        assert indexer.name == "opensearch_indexer"

    def test_version(self, indexer):
        assert indexer.version == "0.1.0"

    def test_config_schema_has_required_keys(self, indexer):
        schema = indexer.config_schema
        assert "host" in schema
        assert "port" in schema
        assert "index_name" in schema
        assert "dimension" in schema


class TestOpenSearchIndexerInvoke:
    @pytest.mark.asyncio
    async def test_empty_embeddings_returns_error(self, indexer, default_config):
        input_data = ComponentResult(data={"embeddings": []})
        result = await indexer.invoke(input_data, default_config)
        assert result.errors
        assert "No embeddings" in result.errors[0]

    @pytest.mark.asyncio
    async def test_missing_opensearch_returns_import_error(self, indexer, sample_embeddings_input, default_config):
        with patch.dict("sys.modules", {"opensearchpy": None}):
            # Force reimport to trigger ImportError
            with patch("builtins.__import__", side_effect=ImportError("No module named 'opensearchpy'")):
                result = await indexer.invoke(sample_embeddings_input, default_config)
                assert result.errors
                assert "opensearch-py not installed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_successful_indexing(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch("opensearchpy.helpers.bulk", return_value=(3, [])):
                result = await indexer.invoke(sample_embeddings_input, default_config)

        assert not result.errors
        assert result.metadata["indexed_count"] == 3
        assert result.metadata["dimensions"] == 1536
        assert result.metadata["index_name"] == "test_index"
        assert result.data["index_name"] == "test_index"

        # Verify index creation was called
        mock_client.indices.create.assert_called_once()
        create_call = mock_client.indices.create.call_args
        assert create_call.kwargs["index"] == "test_index"

    @pytest.mark.asyncio
    async def test_overwrite_deletes_existing_index(self, indexer, sample_embeddings_input):
        config = {
            "host": "localhost",
            "port": 9200,
            "index_name": "test_index",
            "dimension": 1536,
            "overwrite": True,
        }
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch("opensearchpy.helpers.bulk", return_value=(3, [])):
                result = await indexer.invoke(sample_embeddings_input, config)

        assert not result.errors
        mock_client.indices.delete.assert_called_once_with(index="test_index")

    @pytest.mark.asyncio
    async def test_skips_delete_when_not_overwrite(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch("opensearchpy.helpers.bulk", return_value=(3, [])):
                result = await indexer.invoke(sample_embeddings_input, default_config)

        assert not result.errors
        mock_client.indices.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_partial_errors(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch("opensearchpy.helpers.bulk", return_value=(2, [{"index": {"error": "mapping"}}])):
                result = await indexer.invoke(sample_embeddings_input, default_config)

        # Should still succeed, just with partial count
        assert not result.errors
        assert result.metadata["indexed_count"] == 2

    @pytest.mark.asyncio
    async def test_index_mapping_has_knn_vector(self, indexer, sample_embeddings_input, default_config):
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False

        with patch("opensearchpy.OpenSearch", return_value=mock_client):
            with patch("opensearchpy.helpers.bulk", return_value=(3, [])):
                await indexer.invoke(sample_embeddings_input, default_config)

        create_call = mock_client.indices.create.call_args
        body = create_call.kwargs.get("body") or create_call[1].get("body")
        mapping_props = body["mappings"]["properties"]
        assert mapping_props["embedding"]["type"] == "knn_vector"
        assert mapping_props["embedding"]["dimension"] == 1536
        assert mapping_props["content"]["type"] == "text"
        assert mapping_props["chunk_id"]["type"] == "keyword"
        assert mapping_props["workspace_id"]["type"] == "keyword"
