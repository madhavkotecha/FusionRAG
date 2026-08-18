from __future__ import annotations

import pytest

WORKSPACE_ID = "test-workspace-id"


@pytest.fixture
async def created_pipeline(client):
    """Helper: create a pipeline and return its JSON response."""
    resp = await client.post(
        "/api/v1/pipelines/",
        json={
            "name": "Test Pipeline",
            "description": "A test pipeline",
            "workspace_id": WORKSPACE_ID,
            "definition": {
                "nodes": [
                    {"id": "n1", "type": "file_loader", "label": "Load"},
                    {"id": "n2", "type": "llm_generator", "label": "Generate"},
                ],
                "edges": [{"source": "n1", "target": "n2"}],
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_pipeline(client):
    resp = await client.post(
        "/api/v1/pipelines/",
        json={
            "name": "My Pipeline",
            "description": "desc",
            "workspace_id": WORKSPACE_ID,
            "definition": {},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Pipeline"
    assert data["status"] == "draft"
    assert data["createdBy"] == "test-user-id"


@pytest.mark.asyncio
async def test_list_pipelines(client, created_pipeline):
    resp = await client.get(
        "/api/v1/pipelines/", params={"workspace_id": WORKSPACE_ID}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_pipelines_all_workspaces(client, created_pipeline):
    """Org admins can list pipelines across all workspaces with workspace_id=all."""
    resp = await client.get(
        "/api/v1/pipelines/", params={"workspace_id": "all"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_pipeline(client, created_pipeline):
    pid = created_pipeline["id"]
    resp = await client.get(
        f"/api/v1/pipelines/{pid}", params={"workspace_id": WORKSPACE_ID}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


@pytest.mark.asyncio
async def test_get_pipeline_not_found(client):
    resp = await client.get(
        "/api/v1/pipelines/nonexistent", params={"workspace_id": WORKSPACE_ID}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_pipeline(client, created_pipeline):
    pid = created_pipeline["id"]
    resp = await client.put(
        f"/api/v1/pipelines/{pid}",
        params={"workspace_id": WORKSPACE_ID},
        json={"name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_pipeline(client, created_pipeline):
    pid = created_pipeline["id"]
    resp = await client.delete(
        f"/api/v1/pipelines/{pid}", params={"workspace_id": WORKSPACE_ID}
    )
    assert resp.status_code == 204

    # Confirm it's gone
    resp = await client.get(
        f"/api/v1/pipelines/{pid}", params={"workspace_id": WORKSPACE_ID}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_version(client, created_pipeline):
    pid = created_pipeline["id"]
    resp = await client.post(
        f"/api/v1/pipelines/{pid}/versions",
        params={"workspace_id": WORKSPACE_ID},
        json={"change_message": "Initial version"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["changeMessage"] == "Initial version"


@pytest.mark.asyncio
async def test_list_versions(client, created_pipeline):
    pid = created_pipeline["id"]
    # Create two versions
    await client.post(
        f"/api/v1/pipelines/{pid}/versions",
        params={"workspace_id": WORKSPACE_ID},
        json={"change_message": "v1"},
    )
    await client.post(
        f"/api/v1/pipelines/{pid}/versions",
        params={"workspace_id": WORKSPACE_ID},
        json={"change_message": "v2"},
    )

    resp = await client.get(
        f"/api/v1/pipelines/{pid}/versions",
        params={"workspace_id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_run_pipeline(client, created_pipeline):
    pid = created_pipeline["id"]
    resp = await client.post(
        f"/api/v1/pipelines/{pid}/run",
        params={"workspace_id": WORKSPACE_ID},
        json={"input_params": {"query": "test"}},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"] is not None


@pytest.mark.asyncio
async def test_list_runs(client, created_pipeline):
    pid = created_pipeline["id"]
    # Trigger a run first
    await client.post(
        f"/api/v1/pipelines/{pid}/run",
        params={"workspace_id": WORKSPACE_ID},
        json={},
    )
    resp = await client.get(
        f"/api/v1/pipelines/{pid}/runs",
        params={"workspace_id": WORKSPACE_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
