from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest


VALID_COMPONENT_PY = '''\
from pipeline_service.framework.decorators import component, step
from pipeline_service.framework.base import CompositeComponent

@component(category="retriever", name="My Custom Retriever",
           description="A custom retriever",
           input_ports=[{"name": "query", "type": "string"}],
           output_ports=[{"name": "documents", "type": "document_list"}])
class MyCustomRetriever(CompositeComponent):
    @step(order=1, name="Fetch")
    async def fetch(self, input_data, config):
        return {"documents": []}
'''

NO_COMPONENT_PY = '''\
class NotAComponent:
    pass
'''


@pytest.mark.asyncio
async def test_list_components_includes_new_fields(client):
    """Components should include source, is_composite, steps, workspace_id."""
    resp = await client.get("/api/v1/components/file_loader")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "is_composite" in data
    assert "steps" in data
    assert "workspace_id" in data
    # Seed components have source="seed" and workspace_id=None
    assert data["source"] == "seed"
    assert data["is_composite"] is False
    assert data["workspace_id"] is None


@pytest.mark.asyncio
async def test_list_components_filter_by_source(client):
    """Filter source=seed should return only seed components."""
    resp = await client.get("/api/v1/components", params={"source": "seed"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    for comp in data:
        assert comp["source"] == "seed"

    # Filter by custom should return nothing (no custom components seeded)
    resp = await client.get("/api/v1/components", params={"source": "custom"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


@pytest.mark.asyncio
async def test_seed_components_have_null_workspace(client):
    """All seed components should have workspace_id=None (mapped from _global)."""
    resp = await client.get("/api/v1/components", params={"source": "seed"})
    assert resp.status_code == 200
    data = resp.json()
    for comp in data:
        assert comp["workspace_id"] is None, f"{comp['type']} has non-null workspace"


@pytest.mark.asyncio
@patch("pipeline_service.api.component_upload.get_minio_client")
@patch("pipeline_service.api.component_upload.ensure_bucket")
@patch("pipeline_service.api.component_upload.upload_component_file")
async def test_upload_non_python_rejected(
    mock_upload, mock_ensure, mock_minio, client
):
    """Uploading a non-.py file should be rejected with 400."""
    resp = await client.post(
        "/api/v1/components/upload",
        params={"workspace_id": "ws-123"},
        files={"file": ("readme.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    assert "Only .py files" in resp.json()["detail"]
    # MinIO should not have been called
    mock_minio.assert_not_called()


@pytest.mark.asyncio
@patch("pipeline_service.api.component_upload.get_minio_client")
@patch("pipeline_service.api.component_upload.ensure_bucket")
@patch("pipeline_service.api.component_upload.upload_component_file")
async def test_upload_no_component_rejected(
    mock_upload, mock_ensure, mock_minio, client
):
    """Uploading a .py file with no @component class should be rejected with 422."""
    resp = await client.post(
        "/api/v1/components/upload",
        params={"workspace_id": "ws-123"},
        files={"file": ("notcomp.py", NO_COMPONENT_PY.encode(), "text/x-python")},
    )
    assert resp.status_code == 422
    assert "No @component" in resp.json()["detail"]
    mock_minio.assert_not_called()
