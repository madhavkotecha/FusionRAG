import json

import pytest
from rrag_ingestion.core.base import ComponentResult
from rrag_ingestion.core.registry import ComponentRegistry

# Default test workspace ID
TEST_WORKSPACE_ID = "ws-test-001"


@pytest.fixture
def registry():
    reg = ComponentRegistry()
    reg.auto_discover()
    return reg


@pytest.fixture
def sample_input():
    return ComponentResult(data={
        "file_paths": ["test.txt"],
        "documents": [],
    })


@pytest.fixture
def sample_chunks_input():
    from rrag_ingestion.models.document import Chunk
    chunks = [
        Chunk(id="c1", document_id="d1", content="The quick brown fox jumps over the lazy dog.", tokens=10, order_index=0),
        Chunk(id="c2", document_id="d1", content="Machine learning is a subset of artificial intelligence.", tokens=9, order_index=1),
    ]
    return ComponentResult(data={"chunks": chunks, "documents": []})


@pytest.fixture
def auth_headers():
    """Headers that simulate a regular authenticated user with developer access."""
    return {
        "X-Auth-User-Id": "test-user-001",
        "X-Auth-Org-Id": "test-org-001",
        "X-Auth-Org-Role": "member",
        "X-Auth-Email": "test@example.com",
        "X-Auth-Workspace-Roles": json.dumps({TEST_WORKSPACE_ID: "developer"}),
    }


@pytest.fixture
def admin_headers():
    """Headers that simulate an org admin user."""
    return {
        "X-Auth-User-Id": "admin-user-001",
        "X-Auth-Org-Id": "test-org-001",
        "X-Auth-Org-Role": "org_admin",
        "X-Auth-Email": "admin@example.com",
        "X-Auth-Workspace-Roles": json.dumps({TEST_WORKSPACE_ID: "admin"}),
    }


@pytest.fixture
def viewer_headers():
    """Headers that simulate a viewer user."""
    return {
        "X-Auth-User-Id": "viewer-user-001",
        "X-Auth-Org-Id": "test-org-001",
        "X-Auth-Org-Role": "member",
        "X-Auth-Email": "viewer@example.com",
        "X-Auth-Workspace-Roles": json.dumps({TEST_WORKSPACE_ID: "viewer"}),
    }


@pytest.fixture
def workspace_id():
    """Default test workspace ID."""
    return TEST_WORKSPACE_ID
