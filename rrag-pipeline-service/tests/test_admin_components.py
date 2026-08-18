from __future__ import annotations

import pytest
from sqlalchemy import select
from unittest.mock import MagicMock

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pipeline_service.database import get_session
from pipeline_service.dependencies import AuthContext, get_current_user
from pipeline_service.main import app
from pipeline_service.models.component_version import ComponentVersion


@pytest.fixture
async def unauthenticated_client(engine):
    """Client with no auth — triggers 401."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override_get_session():
        async with session_factory() as session:
            yield session
    app.dependency_overrides[get_session] = override_get_session
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    app.state.redis = mock_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def member_auth() -> AuthContext:
    return AuthContext(
        user_id="member-user-id", org_id="test-org-id", org_role="member",
        email="member@example.com", workspace_roles={"test-workspace-id": "viewer"},
        is_platform_admin=False,
    )


@pytest.fixture
async def member_client(engine, member_auth):
    """Client with member role — triggers 403 on admin endpoints."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override_get_session():
        async with session_factory() as session:
            yield session
    async def override_get_current_user():
        return member_auth
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    app.state.redis = mock_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def platform_admin_auth() -> AuthContext:
    return AuthContext(
        user_id="platform-admin-id", org_id="test-org-id", org_role="org_admin",
        email="platformadmin@example.com", workspace_roles={},
        is_platform_admin=True,
    )


@pytest.fixture
async def platform_admin_client(engine, platform_admin_auth):
    """Client with platform_admin — can edit seed components."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def override_get_session():
        async with session_factory() as session:
            yield session
    async def override_get_current_user():
        return platform_admin_auth
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    app.state.redis = mock_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_version(db_session):
    from pipeline_service.services.component_versions import create_version

    ver = await create_version(
        db=db_session,
        component_type="file_loader",
        workspace_id="_global",
        code="# test code",
        changed_by="test-user",
        change_reason="initial",
    )
    assert ver.version == 1
    assert ver.component_type == "file_loader"
    assert ver.code == "# test code"
    assert ver.changed_by == "test-user"


@pytest.mark.asyncio
async def test_create_version_increments(db_session):
    from pipeline_service.services.component_versions import create_version

    v1 = await create_version(
        db=db_session,
        component_type="web_scraper",
        workspace_id="_global",
        code="# v1",
        changed_by="user-a",
    )
    v2 = await create_version(
        db=db_session,
        component_type="web_scraper",
        workspace_id="_global",
        code="# v2",
        changed_by="user-b",
    )
    assert v1.version == 1
    assert v2.version == 2


@pytest.mark.asyncio
async def test_list_versions(db_session):
    from pipeline_service.services.component_versions import (
        create_version,
        list_versions,
    )

    await create_version(
        db=db_session,
        component_type="dense_retriever",
        workspace_id="_global",
        code="# v1",
        changed_by="user-a",
    )
    await create_version(
        db=db_session,
        component_type="dense_retriever",
        workspace_id="_global",
        code="# v2",
        changed_by="user-b",
    )

    versions, total = await list_versions(
        db=db_session,
        component_type="dense_retriever",
        workspace_id="_global",
    )
    assert total == 2
    assert versions[0].version == 2  # newest first
    assert versions[1].version == 1


@pytest.mark.asyncio
async def test_get_version_code(db_session):
    from pipeline_service.services.component_versions import (
        create_version,
        get_version_code,
    )

    await create_version(
        db=db_session,
        component_type="llm_generator",
        workspace_id="_global",
        code="# original code",
        changed_by="user-a",
    )

    code = await get_version_code(
        db=db_session,
        component_type="llm_generator",
        workspace_id="_global",
        version=1,
    )
    assert code == "# original code"


@pytest.mark.asyncio
async def test_get_version_code_not_found(db_session):
    from pipeline_service.services.component_versions import get_version_code

    code = await get_version_code(
        db=db_session,
        component_type="nonexistent",
        workspace_id="_global",
        version=99,
    )
    assert code is None


# ── Admin API endpoint tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_components(client):
    resp = await client.get("/api/v1/admin/components")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10

@pytest.mark.asyncio
async def test_admin_list_filter_source(client):
    resp = await client.get("/api/v1/admin/components?source=seed")
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["source"] == "seed" for c in data)

@pytest.mark.asyncio
async def test_admin_list_filter_category(client):
    resp = await client.get("/api/v1/admin/components?category=parser")
    assert resp.status_code == 200
    data = resp.json()
    assert all(c["category"] == "parser" for c in data)

@pytest.mark.asyncio
async def test_admin_list_search(client):
    resp = await client.get("/api/v1/admin/components?search=loader")
    assert resp.status_code == 200
    data = resp.json()
    assert any("loader" in c["name"].lower() or "loader" in c["type"].lower() for c in data)

@pytest.mark.asyncio
async def test_admin_list_unauthenticated(unauthenticated_client):
    resp = await unauthenticated_client.get("/api/v1/admin/components")
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_admin_list_non_admin(member_client):
    resp = await member_client.get("/api/v1/admin/components")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_admin_get_code(client):
    resp = await client.get("/api/v1/admin/components/file_loader/code", params={"workspace_id": "_global"})
    assert resp.status_code in (200, 404)

@pytest.mark.asyncio
async def test_admin_list_versions_empty(client):
    resp = await client.get("/api/v1/admin/components/file_loader/versions", params={"workspace_id": "_global"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []

@pytest.mark.asyncio
async def test_admin_revert_not_found(platform_admin_client):
    resp = await platform_admin_client.post("/api/v1/admin/components/file_loader/revert", params={"workspace_id": "_global"}, json={"version": 99})
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_admin_update_code_invalid_syntax(platform_admin_client):
    resp = await platform_admin_client.put("/api/v1/admin/components/file_loader/code", params={"workspace_id": "_global"}, json={"code": "def broken(:", "change_reason": "test"})
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_admin_update_code_no_decorator(platform_admin_client):
    resp = await platform_admin_client.put("/api/v1/admin/components/file_loader/code", params={"workspace_id": "_global"}, json={"code": "class Foo:\n    pass", "change_reason": "test"})
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_member_cannot_edit_seed(member_client):
    resp = await member_client.get("/api/v1/admin/components")
    assert resp.status_code == 403
