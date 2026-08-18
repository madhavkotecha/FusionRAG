"""Tests for query pipeline features: type filter, compiler, and sync.

Covers:
1. Create pipeline with pipeline_type=query and datastore_id
2. List pipelines filtered by pipeline_type
3. Query pipeline compiler (unit tests)
4. Update preserves pipeline_type
"""
from __future__ import annotations

import pytest

WORKSPACE_ID = "test-workspace-id"


# ── 1. Query Pipeline CRUD ──────────────────────────────────────────────


@pytest.fixture
async def query_pipeline(client):
    """Create a query pipeline and return its JSON response."""
    resp = await client.post(
        "/api/v1/pipelines/",
        json={
            "name": "Test Query Pipeline",
            "description": "A test query pipeline",
            "workspace_id": WORKSPACE_ID,
            "pipeline_type": "query",
            "datastore_id": "ds-test-123",
            "definition": {
                "nodes": [
                    {
                        "id": "n1",
                        "type": "dense_retriever",
                        "data": {
                            "category": "retriever",
                            "componentType": "dense_retriever",
                            "label": "Dense Retriever",
                            "config": {"top_k": 10},
                        },
                    },
                    {
                        "id": "n2",
                        "type": "cross_encoder_reranker",
                        "data": {
                            "category": "reranker",
                            "componentType": "cross_encoder_reranker",
                            "label": "Cross-Encoder",
                            "config": {"top_k": 5},
                        },
                    },
                    {
                        "id": "n3",
                        "type": "llm_generator",
                        "data": {
                            "category": "generator",
                            "componentType": "llm_generator",
                            "label": "LLM Generator",
                            "config": {"model": "gpt-4o", "temperature": 0.1},
                        },
                    },
                ],
                "edges": [
                    {"source": "n1", "target": "n2"},
                    {"source": "n2", "target": "n3"},
                ],
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def ingestion_pipeline(client):
    """Create an ingestion pipeline for filtering tests."""
    resp = await client.post(
        "/api/v1/pipelines/",
        json={
            "name": "Test Ingestion Pipeline",
            "workspace_id": WORKSPACE_ID,
            "pipeline_type": "ingestion",
            "definition": {"nodes": [], "edges": []},
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_query_pipeline(client):
    resp = await client.post(
        "/api/v1/pipelines/",
        json={
            "name": "My Query Pipeline",
            "description": "desc",
            "workspace_id": WORKSPACE_ID,
            "pipeline_type": "query",
            "datastore_id": "ds-abc-123",
            "definition": {},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Query Pipeline"
    assert data["pipelineType"] == "query"
    assert data["datastoreId"] == "ds-abc-123"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_create_ingestion_pipeline_defaults(client):
    """When pipeline_type is omitted, it defaults to ingestion."""
    resp = await client.post(
        "/api/v1/pipelines/",
        json={
            "name": "Default Type Pipeline",
            "workspace_id": WORKSPACE_ID,
            "definition": {},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["pipelineType"] == "ingestion"
    assert data["datastoreId"] is None


# ── 2. Pipeline Type Filtering ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_filters_by_type(client, query_pipeline, ingestion_pipeline):
    # List only query pipelines
    resp = await client.get(
        "/api/v1/pipelines/",
        params={"workspace_id": WORKSPACE_ID, "pipeline_type": "query"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["pipelineType"] == "query" for p in data)
    assert any(p["id"] == query_pipeline["id"] for p in data)
    assert not any(p["id"] == ingestion_pipeline["id"] for p in data)


@pytest.mark.asyncio
async def test_list_filters_ingestion_only(client, query_pipeline, ingestion_pipeline):
    resp = await client.get(
        "/api/v1/pipelines/",
        params={"workspace_id": WORKSPACE_ID, "pipeline_type": "ingestion"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(p["pipelineType"] == "ingestion" for p in data)
    assert any(p["id"] == ingestion_pipeline["id"] for p in data)
    assert not any(p["id"] == query_pipeline["id"] for p in data)


@pytest.mark.asyncio
async def test_list_no_filter_returns_all(client, query_pipeline, ingestion_pipeline):
    resp = await client.get(
        "/api/v1/pipelines/",
        params={"workspace_id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    ids = [p["id"] for p in data]
    assert query_pipeline["id"] in ids
    assert ingestion_pipeline["id"] in ids


# ── 3. Update preserves pipeline type ──────────────────────────────────


@pytest.mark.asyncio
async def test_update_query_pipeline(client, query_pipeline):
    pid = query_pipeline["id"]
    resp = await client.put(
        f"/api/v1/pipelines/{pid}",
        params={"workspace_id": WORKSPACE_ID},
        json={"name": "Updated Query Pipeline", "datastore_id": "ds-new-456"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Query Pipeline"
    assert data["datastoreId"] == "ds-new-456"
    assert data["pipelineType"] == "query"


# ── 4. Query Pipeline Compiler ──────────────────────────────────────────


class TestQueryPipelineCompiler:
    def test_compile_empty_definition(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="Test",
            description="desc",
            datastore_id="ds-1",
            definition={"nodes": [], "edges": []},
        )
        assert result["name"] == "Test"
        assert result["description"] == "desc"
        assert result["datastore_id"] == "ds-1"
        assert result["retrieval_strategy"] == "auto"
        assert "retriever" not in result
        assert "reranker" not in result

    def test_compile_dense_retriever(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="Dense",
            description=None,
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "retriever",
                            "componentType": "dense_retriever",
                            "config": {"top_k": 15},
                        },
                    },
                ],
                "edges": [],
            },
        )
        assert result["retrieval_strategy"] == "dense"
        assert result["retriever"]["strategy"] == "dense"
        assert result["retriever"]["top_k"] == 15

    def test_compile_hybrid_from_multiple_retrievers(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="Hybrid",
            description=None,
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "retriever",
                            "componentType": "dense_retriever",
                            "config": {},
                        },
                    },
                    {
                        "id": "n2",
                        "data": {
                            "category": "retriever",
                            "componentType": "graph_retriever",
                            "config": {},
                        },
                    },
                ],
                "edges": [],
            },
        )
        assert result["retrieval_strategy"] == "hybrid"

    def test_compile_reranker(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="With Reranker",
            description=None,
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "reranker",
                            "componentType": "cohere_reranker",
                            "config": {"top_k": 5},
                        },
                    },
                ],
                "edges": [],
            },
        )
        assert result["reranker"]["enabled"] is True
        assert result["reranker"]["strategy"] == "cohere"
        assert result["reranker"]["top_k"] == 5

    def test_compile_planner(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="With Planner",
            description=None,
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "planner",
                            "componentType": "mcts_planner",
                            "config": {"max_hops": 5},
                        },
                    },
                ],
                "edges": [],
            },
        )
        assert result["planner"]["enabled"] is True
        assert result["planner"]["strategy"] == "mcts"
        assert result["planner"]["max_hops"] == 5

    def test_compile_agent(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="With Agent",
            description=None,
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "agent",
                            "componentType": "reflection_agent",
                            "config": {"max_retries": 2},
                        },
                    },
                ],
                "edges": [],
            },
        )
        assert result["agent"]["enabled"] is True
        assert result["agent"]["agent_type"] == "reflection"
        assert result["agent"]["max_retries"] == 2

    def test_compile_full_pipeline(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="Full Pipeline",
            description="Complete",
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "retriever",
                            "componentType": "hybrid_retriever",
                            "config": {"top_k": 20, "alpha": 0.7},
                        },
                    },
                    {
                        "id": "n2",
                        "data": {
                            "category": "reranker",
                            "componentType": "cross_encoder_reranker",
                            "config": {"top_k": 5},
                        },
                    },
                    {
                        "id": "n3",
                        "data": {
                            "category": "generator",
                            "componentType": "llm_generator",
                            "config": {"model": "gpt-4o", "temperature": 0.0},
                        },
                    },
                ],
                "edges": [
                    {"source": "n1", "target": "n2"},
                    {"source": "n2", "target": "n3"},
                ],
            },
        )
        assert result["retrieval_strategy"] == "hybrid"
        assert result["retriever"]["strategy"] == "hybrid"
        assert result["retriever"]["alpha"] == 0.7
        assert result["reranker"]["enabled"] is True
        assert result["reranker"]["strategy"] == "cross_encoder"
        assert result["generator"]["model"] == "gpt-4o"
        assert result["generator"]["temperature"] == 0.0
        assert result["definition"] is not None

    def test_compile_graph_retriever(self):
        from pipeline_service.services.query_pipeline_compiler import (
            compile_query_pipeline,
        )

        result = compile_query_pipeline(
            pipeline_id="p1",
            name="Graph",
            description=None,
            datastore_id="ds-1",
            definition={
                "nodes": [
                    {
                        "id": "n1",
                        "data": {
                            "category": "retriever",
                            "componentType": "graph_retriever",
                            "config": {"graph_search_depth": 3},
                        },
                    },
                ],
                "edges": [],
            },
        )
        assert result["retrieval_strategy"] == "graph"
        assert result["retriever"]["strategy"] == "graph"
