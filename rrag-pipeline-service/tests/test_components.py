from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_components(client):
    resp = await client.get("/api/v1/components/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10  # Expanded registry has many more
    # Verify component structure
    component = data[0]
    assert "type" in component
    assert "category" in component
    assert "name" in component
    assert "description" in component
    assert "config_schema" in component
    assert "input_ports" in component
    assert "output_ports" in component


@pytest.mark.asyncio
async def test_get_specific_component(client):
    resp = await client.get("/api/v1/components/file_loader")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "file_loader"
    assert data["category"] == "parser"
    assert data["name"] == "File Loader"


@pytest.mark.asyncio
async def test_get_component_not_found(client):
    resp = await client.get("/api/v1/components/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_component_categories(client):
    resp = await client.get("/api/v1/components/")
    data = resp.json()
    categories = {c["category"] for c in data}
    expected = {
        "parser", "chunker", "embedder", "extractor",
        "indexer", "graph_builder", "storage",
        "retriever", "reranker", "generator", "planner", "agent",
    }
    assert categories == expected


@pytest.mark.asyncio
async def test_each_component_type(client):
    expected_types = [
        "file_loader",
        "web_scraper",
        "recursive_chunker",
        "semantic_chunker",
        "openai_embedder",
        "sentence_transformer_embedder",
        "dense_retriever",
        "hybrid_retriever",
        "cross_encoder_reranker",
        "llm_generator",
    ]
    for comp_type in expected_types:
        resp = await client.get(f"/api/v1/components/{comp_type}")
        assert resp.status_code == 200, f"Failed for component type: {comp_type}"
        assert resp.json()["type"] == comp_type
