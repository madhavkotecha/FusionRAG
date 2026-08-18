from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pipeline_service.database import get_session
from pipeline_service.dependencies import AuthContext, get_current_user
from pipeline_service.main import app
from pipeline_service.models import Base
from pipeline_service.models.component import Component
from pipeline_service.models.component_version import ComponentVersion  # noqa: F401
from pipeline_service.models.template import PipelineTemplate

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed components and templates into the test DB
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        from pipeline_service.services.component_registry import SEED_COMPONENTS
        from pipeline_service.services.template_store import SEED_TEMPLATES

        for comp_data in SEED_COMPONENTS:
            session.add(Component(**comp_data))
        for tmpl_data in SEED_TEMPLATES:
            session.add(PipelineTemplate(**tmpl_data))
        await session.commit()

    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_auth() -> AuthContext:
    return AuthContext(
        user_id="test-user-id",
        org_id="test-org-id",
        org_role="org_admin",
        email="test@example.com",
        workspace_roles={"test-workspace-id": "editor"},
    )


@pytest.fixture
async def client(engine, mock_auth) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    async def override_get_current_user() -> AuthContext:
        return mock_auth

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Provide a mock Redis so route handlers can access request.app.state.redis
    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # Cache miss by default
    app.state.redis = mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
