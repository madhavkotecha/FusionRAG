"""End-to-end tests for the superadmin interface.

Verifies:
1. Admin stats endpoint returns system overview
2. Queue stats with detailed metrics
3. Queue admin actions (purge, retry)
4. Service health check
5. System configuration CRUD
6. Queue timeline for charting
7. Admin dashboard data flow
8. Queue management data flow
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# rq uses Unix signals which don't work on Windows, mock it before import
if sys.platform == "win32":
    _rq_mock = MagicMock()
    sys.modules["rq"] = _rq_mock
    sys.modules["rq.queue"] = _rq_mock
    sys.modules["rq.job"] = _rq_mock
    sys.modules["rq.worker"] = _rq_mock

from fastapi.testclient import TestClient  # noqa: E402
from rrag_ingestion.main import app  # noqa: E402

TEST_WORKSPACE_ID = "ws-test-001"

ADMIN_HEADERS = {
    "X-Auth-User-Id": "admin-user-001",
    "X-Auth-Org-Id": "test-org-001",
    "X-Auth-Org-Role": "org_admin",
    "X-Auth-Email": "admin@example.com",
    "X-Auth-Workspace-Roles": json.dumps({TEST_WORKSPACE_ID: "admin"}),
}

AUTH_HEADERS = {
    "X-Auth-User-Id": "test-user-001",
    "X-Auth-Org-Id": "test-org-001",
    "X-Auth-Org-Role": "member",
    "X-Auth-Email": "test@example.com",
    "X-Auth-Workspace-Roles": json.dumps({TEST_WORKSPACE_ID: "developer"}),
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_db(client):
    """Ensure database state is clean for each test."""
    yield
    # Clean up test jobs from PostgreSQL
    from rrag_ingestion.db.models import JobRow
    from rrag_ingestion.db.session import get_session_factory
    import asyncio

    async def _cleanup():
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import delete
            await session.execute(delete(JobRow).where(JobRow.id.like("test-%")))
            await session.commit()

    try:
        asyncio.get_event_loop().run_until_complete(_cleanup())
    except Exception:
        pass


def _create_test_job(client, job_id: str, status: str = "completed", **overrides) -> dict:
    """Helper to create a test job in PostgreSQL."""
    from datetime import datetime, timezone
    from rrag_ingestion.db.models import JobRow
    from rrag_ingestion.db.session import get_session_factory
    import asyncio

    now = datetime.now(timezone.utc)
    job_data = {
        "id": job_id,
        "workspace_id": "",
        "pipeline_name": "test-pipeline",
        "document_ids": ["doc-1"],
        "config_overrides": {},
        "status": status,
        "progress": 100 if status == "completed" else 0,
        "current_step": None,
        "total_steps": 3,
        "errors": ["Test error"] if status == "failed" else [],
        "step_results": [],
        "pipeline_steps": [],
        "total_duration_ms": 1500 if status == "completed" else None,
        "datastore_id": None,
    }
    job_data.update(overrides)

    async def _insert():
        factory = get_session_factory()
        async with factory() as session:
            row = JobRow(
                id=job_id,
                workspace_id=job_data.get("workspace_id", ""),
                pipeline_name=job_data["pipeline_name"],
                document_ids=job_data["document_ids"],
                config_overrides=job_data["config_overrides"],
                status=status,
                progress=job_data["progress"],
                total_steps=job_data["total_steps"],
                errors=job_data["errors"],
                step_results=job_data["step_results"],
                pipeline_steps=job_data["pipeline_steps"],
                total_duration_ms=job_data["total_duration_ms"],
                datastore_id=job_data["datastore_id"],
                created_at=now,
                started_at=now if status != "queued" else None,
                completed_at=now if status in ("completed", "failed") else None,
            )
            session.add(row)
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_insert())

    # Return a dict matching old format for assertions
    job_data["created_at"] = now.isoformat()
    job_data["started_at"] = now.isoformat() if status != "queued" else None
    job_data["completed_at"] = now.isoformat() if status in ("completed", "failed") else None
    return job_data


def _delete_test_jobs(*job_ids: str) -> None:
    """Delete test jobs from PostgreSQL by ID."""
    from rrag_ingestion.db.models import JobRow
    from rrag_ingestion.db.session import get_session_factory
    import asyncio

    async def _do():
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import delete
            await session.execute(delete(JobRow).where(JobRow.id.in_(list(job_ids))))
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_do())


def _job_exists(job_id: str) -> bool:
    """Check if a job exists in PostgreSQL."""
    from rrag_ingestion.db.models import JobRow
    from rrag_ingestion.db.session import get_session_factory
    import asyncio

    async def _do():
        factory = get_session_factory()
        async with factory() as session:
            row = await session.get(JobRow, job_id)
            return row is not None

    return asyncio.get_event_loop().run_until_complete(_do())


# -- Test 1: System Stats -------------------------------------------------------


class TestAdminStats:
    def test_stats_returns_system_overview(self, client):
        """GET /admin/stats returns aggregate system stats."""
        resp = client.get("/api/v1/ingestion/admin/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()

        assert "totalJobs" in data
        assert "jobsByStatus" in data
        assert "totalDocuments" in data
        assert "totalDataStores" in data
        assert "totalPipelines" in data
        assert "totalQueryPipelines" in data
        assert "redisConnected" in data
        assert "uptimeSeconds" in data
        assert isinstance(data["totalJobs"], int)
        assert isinstance(data["jobsByStatus"], dict)
        assert data["redisConnected"] is True

    def test_stats_reflects_created_jobs(self, client):
        """Stats should count jobs created in Redis."""
        _create_test_job(client, "test-stats-1", "completed")
        _create_test_job(client, "test-stats-2", "failed")
        _create_test_job(client, "test-stats-3", "running")

        resp = client.get("/api/v1/ingestion/admin/stats", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["totalJobs"] >= 3
        assert data["jobsByStatus"].get("completed", 0) >= 1
        assert data["jobsByStatus"].get("failed", 0) >= 1
        assert data["jobsByStatus"].get("running", 0) >= 1

        # Cleanup
        for jid in ("test-stats-1", "test-stats-2", "test-stats-3"):
            redis.delete(f"rrag:job:{jid}")

    def test_stats_uptime_positive(self, client):
        """Uptime should be a positive number."""
        resp = client.get("/api/v1/ingestion/admin/stats", headers=ADMIN_HEADERS)
        assert resp.json()["uptimeSeconds"] > 0

    def test_stats_requires_auth(self, client):
        """Stats endpoint should require authentication."""
        resp = client.get("/api/v1/ingestion/admin/stats")
        assert resp.status_code == 401

    def test_stats_requires_admin(self, client):
        """Stats endpoint should require org admin role."""
        resp = client.get("/api/v1/ingestion/admin/stats", headers=AUTH_HEADERS)
        assert resp.status_code == 403


# -- Test 2: Queue Stats -------------------------------------------------------


class TestQueueStats:
    def test_queue_stats_returns_detailed_metrics(self, client):
        """GET /admin/queue/stats returns queue metrics."""
        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()

        assert "totalJobs" in data
        assert "queued" in data
        assert "running" in data
        assert "completed" in data
        assert "failed" in data
        assert "cancelled" in data
        assert "avgDurationMs" in data
        assert "recentThroughput" in data
        assert "oldestQueuedAge" in data

    def test_queue_stats_with_jobs(self, client):
        """Queue stats should reflect actual job counts."""
        _create_test_job(client, "test-qs-1", "queued")
        _create_test_job(client, "test-qs-2", "completed")
        _create_test_job(client, "test-qs-3", "failed")

        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["queued"] >= 1
        assert data["completed"] >= 1
        assert data["failed"] >= 1
        assert data["totalJobs"] >= 3

        # Cleanup
        for jid in ("test-qs-1", "test-qs-2", "test-qs-3"):
            redis.delete(f"rrag:job:{jid}")

    def test_avg_duration_calculated(self, client):
        """Average duration should be calculated from completed jobs."""
        _create_test_job(client, "test-dur-1", "completed", total_duration_ms=1000)
        _create_test_job(client, "test-dur-2", "completed", total_duration_ms=3000)

        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["avgDurationMs"] is not None
        # Average of 1000 and 3000 = 2000 (approximately, may include other jobs)
        assert data["avgDurationMs"] > 0

        for jid in ("test-dur-1", "test-dur-2"):
            redis.delete(f"rrag:job:{jid}")


# -- Test 3: Queue Actions -----------------------------------------------------


class TestQueueActions:
    def test_purge_failed_jobs(self, client):
        """POST /admin/queue/actions with purge_failed removes failed jobs."""
        _create_test_job(client, "test-pf-1", "failed")
        _create_test_job(client, "test-pf-2", "failed")
        _create_test_job(client, "test-pf-3", "completed")

        resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
            "action": "purge_failed",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "purge_failed"
        assert data["affected"] >= 2
        assert "Purged" in data["message"]

        # Verify failed jobs are gone but completed remains
        assert redis.get("rrag:job:test-pf-1") is None
        assert redis.get("rrag:job:test-pf-2") is None
        assert redis.get("rrag:job:test-pf-3") is not None

        redis.delete("rrag:job:test-pf-3")

    def test_purge_completed_jobs(self, client):
        """POST /admin/queue/actions with purge_completed removes completed jobs."""
        _create_test_job(client, "test-pc-1", "completed")
        _create_test_job(client, "test-pc-2", "running")

        resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
            "action": "purge_completed",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "purge_completed"
        assert data["affected"] >= 1

        # Running job should remain
        assert redis.get("rrag:job:test-pc-2") is not None

        redis.delete("rrag:job:test-pc-2")

    def test_purge_all_finished(self, client):
        """POST /admin/queue/actions with purge_all removes completed+failed+cancelled."""
        _create_test_job(client, "test-pa-1", "completed")
        _create_test_job(client, "test-pa-2", "failed")
        _create_test_job(client, "test-pa-3", "cancelled")
        _create_test_job(client, "test-pa-4", "running")

        resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
            "action": "purge_all",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["affected"] >= 3

        # Running job should remain
        assert redis.get("rrag:job:test-pa-4") is not None

        redis.delete("rrag:job:test-pa-4")

    def test_unknown_action_returns_400(self, client):
        """Unknown queue action should return 400."""
        resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
            "action": "unknown_action",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 400

    def test_retry_all_failed(self, client):
        """POST /admin/queue/actions with retry_all_failed re-enqueues failed jobs."""
        _create_test_job(client, "test-rf-1", "failed")

        with patch("rrag_ingestion.api.admin.enqueue_pipeline_job") as mock_enqueue:
            mock_enqueue.return_value = "new-job-id"
            resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
                "action": "retry_all_failed",
            }, headers=ADMIN_HEADERS)
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "retry_all_failed"
            assert data["affected"] >= 1
            assert "Retrying" in data["message"]

        redis.delete("rrag:job:test-rf-1")


# -- Test 4: Service Health ----------------------------------------------------


class TestServiceHealth:
    def test_health_check_returns_services(self, client):
        """GET /admin/health returns service health info."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()

        assert "overall" in data
        assert data["overall"] in ("healthy", "degraded", "down")
        assert "services" in data
        assert isinstance(data["services"], list)
        assert len(data["services"]) >= 1
        assert "checkedAt" in data

    def test_health_includes_redis(self, client):
        """Health check should include Redis status."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        data = resp.json()

        redis_service = next(
            (s for s in data["services"] if s["name"] == "Redis"), None
        )
        assert redis_service is not None
        assert redis_service["status"] == "healthy"
        assert redis_service["responseTimeMs"] is not None
        assert redis_service["version"] is not None

    def test_health_service_structure(self, client):
        """Each service in health response should have required fields."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        data = resp.json()

        for service in data["services"]:
            assert "name" in service
            assert "status" in service
            assert service["status"] in ("healthy", "degraded", "down")
            assert "url" in service
            assert "responseTimeMs" in service
            assert "version" in service

    def test_health_ingestion_service_listed(self, client):
        """The ingestion service should be listed in health check."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        data = resp.json()

        ingestion = next(
            (s for s in data["services"] if "Ingestion" in s["name"]), None
        )
        assert ingestion is not None
        # In test environment, the service may be down since TestClient doesn't serve HTTP
        assert ingestion["status"] in ("healthy", "degraded", "down")


# -- Test 5: System Configuration -----------------------------------------------


class TestSystemConfig:
    def test_get_config_returns_all_sections(self, client):
        """GET /admin/config returns complete configuration."""
        resp = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()

        assert "llm" in data
        assert "embedding" in data
        assert "queue" in data
        assert "storage" in data

        assert "defaultModel" in data["llm"]
        assert "hasApiKey" in data["llm"]
        assert "defaultModel" in data["embedding"]
        assert "name" in data["queue"]
        assert "jobTimeout" in data["queue"]
        assert "storageDir" in data["storage"]
        assert "maxUploadSizeMb" in data["storage"]

    def test_update_llm_model(self, client):
        """PUT /admin/config updates LLM model setting."""
        # Save original
        orig = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS).json()
        orig_model = orig["llm"]["defaultModel"]

        resp = client.put("/api/v1/ingestion/admin/config", json={
            "defaultLlmModel": "gpt-4o",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"]["defaultLlmModel"] == "gpt-4o"

        # Verify change persisted
        check = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS).json()
        assert check["llm"]["defaultModel"] == "gpt-4o"

        # Restore
        client.put("/api/v1/ingestion/admin/config", json={
            "defaultLlmModel": orig_model,
        }, headers=ADMIN_HEADERS)

    def test_update_embedding_model(self, client):
        """PUT /admin/config updates embedding model setting."""
        orig = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS).json()
        orig_model = orig["embedding"]["defaultModel"]

        resp = client.put("/api/v1/ingestion/admin/config", json={
            "defaultEmbeddingModel": "text-embedding-3-large",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["updated"]["defaultEmbeddingModel"] == "text-embedding-3-large"

        # Restore
        client.put("/api/v1/ingestion/admin/config", json={
            "defaultEmbeddingModel": orig_model,
        }, headers=ADMIN_HEADERS)

    def test_update_job_timeout(self, client):
        """PUT /admin/config updates queue job timeout."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "rqJobTimeout": 7200,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["updated"]["rqJobTimeout"] == 7200

        check = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS).json()
        assert check["queue"]["jobTimeout"] == 7200

        # Restore
        client.put("/api/v1/ingestion/admin/config", json={
            "rqJobTimeout": 3600,
        }, headers=ADMIN_HEADERS)

    def test_update_max_upload_size(self, client):
        """PUT /admin/config updates max upload size."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "maxUploadSizeMb": 200,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["updated"]["maxUploadSizeMb"] == 200

        check = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS).json()
        assert check["storage"]["maxUploadSizeMb"] == 200

        # Restore
        client.put("/api/v1/ingestion/admin/config", json={
            "maxUploadSizeMb": 100,
        }, headers=ADMIN_HEADERS)

    def test_update_multiple_settings(self, client):
        """PUT /admin/config can update multiple settings at once."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "defaultLlmModel": "gpt-4-turbo",
            "maxUploadSizeMb": 50,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        updated = resp.json()["updated"]
        assert updated["defaultLlmModel"] == "gpt-4-turbo"
        assert updated["maxUploadSizeMb"] == 50

        # Restore
        client.put("/api/v1/ingestion/admin/config", json={
            "defaultLlmModel": "gpt-4o-mini",
            "maxUploadSizeMb": 100,
        }, headers=ADMIN_HEADERS)

    def test_update_empty_body_returns_400(self, client):
        """PUT /admin/config with no changes should return 400."""
        resp = client.put("/api/v1/ingestion/admin/config", json={}, headers=ADMIN_HEADERS)
        assert resp.status_code == 400

    def test_config_hides_sensitive_data(self, client):
        """Config endpoint should not expose full API keys or passwords."""
        resp = client.get("/api/v1/ingestion/admin/config", headers=ADMIN_HEADERS)
        data = resp.json()
        # Should only expose hasApiKey boolean, not the actual key
        assert isinstance(data["llm"]["hasApiKey"], bool)
        assert "apiKey" not in str(data)
        # Redis URL should not contain password
        redis_url = data["queue"]["redisUrl"]
        assert "@" not in redis_url or "password" not in redis_url


# -- Test 6: Queue Timeline ----------------------------------------------------


class TestQueueTimeline:
    def test_timeline_returns_hourly_buckets(self, client):
        """GET /admin/queue/timeline returns hourly job data."""
        resp = client.get("/api/v1/ingestion/admin/queue/timeline", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()

        assert "timeline" in data
        assert "hours" in data
        assert isinstance(data["timeline"], list)
        assert data["hours"] == 24

    def test_timeline_custom_hours(self, client):
        """Timeline should respect custom hours parameter."""
        resp = client.get("/api/v1/ingestion/admin/queue/timeline", params={"hours": 12}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["hours"] == 12

    def test_timeline_entries_have_required_fields(self, client):
        """Each timeline entry should have hour, completed, failed, created."""
        _create_test_job(client, "test-tl-1", "completed")

        resp = client.get("/api/v1/ingestion/admin/queue/timeline", headers=ADMIN_HEADERS)
        data = resp.json()

        if data["timeline"]:
            entry = data["timeline"][0]
            assert "hour" in entry
            assert "completed" in entry
            assert "failed" in entry
            assert "created" in entry

        redis.delete("rrag:job:test-tl-1")


# -- Test 7: Admin Dashboard Data Flow -----------------------------------------


class TestAdminDashboard:
    """Tests verifying data that powers the admin dashboard UI."""

    def test_dashboard_stats_all_zero_on_empty(self, client):
        """On a fresh system, stats should have zero or positive counts."""
        resp = client.get("/api/v1/ingestion/admin/stats", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["totalJobs"] >= 0
        assert data["totalDocuments"] >= 0
        assert data["totalDataStores"] >= 0

    def test_dashboard_queue_stats_consistent(self, client):
        """Queue stats should be consistent with total."""
        _create_test_job(client, "test-dc-1", "completed")
        _create_test_job(client, "test-dc-2", "queued")

        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        data = resp.json()
        component_sum = data["queued"] + data["running"] + data["completed"] + data["failed"] + data["cancelled"]
        assert component_sum == data["totalJobs"]

        for jid in ("test-dc-1", "test-dc-2"):
            redis.delete(f"rrag:job:{jid}")


# -- Test 8: Queue Management Data Flow ----------------------------------------


class TestQueueManagement:
    """Tests verifying data that powers the queue management UI."""

    def test_jobs_list_endpoint_works(self, client):
        """The existing /jobs endpoint used by the queue page should work."""
        resp = client.get(
            "/api/v1/ingestion/jobs",
            params={"workspace_id": TEST_WORKSPACE_ID},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert "jobs" in resp.json()

    def test_jobs_with_status_filter(self, client):
        """Jobs endpoint with status filter should work."""
        redis = app.state.redis
        # Create workspace-scoped jobs
        _create_test_job(client, "test-jf-1", "completed", workspace_id=TEST_WORKSPACE_ID)
        redis.set(f"rrag:job:{TEST_WORKSPACE_ID}:test-jf-1", redis.get("rrag:job:test-jf-1"))
        _create_test_job(client, "test-jf-2", "failed", workspace_id=TEST_WORKSPACE_ID)
        redis.set(f"rrag:job:{TEST_WORKSPACE_ID}:test-jf-2", redis.get("rrag:job:test-jf-2"))

        resp = client.get(
            "/api/v1/ingestion/jobs",
            params={"status": "failed", "workspace_id": TEST_WORKSPACE_ID},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        jobs = resp.json()["jobs"]
        for j in jobs:
            assert j["status"] == "failed"

        for jid in ("test-jf-1", "test-jf-2"):
            redis.delete(f"rrag:job:{jid}")
            redis.delete(f"rrag:job:{TEST_WORKSPACE_ID}:{jid}")

    def test_admin_actions_then_verify_queue(self, client):
        """Create jobs, purge some, verify queue reflects changes."""
        _create_test_job(client, "test-av-1", "completed")
        _create_test_job(client, "test-av-2", "failed")
        _create_test_job(client, "test-av-3", "running")

        # Purge completed
        resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
            "action": "purge_completed",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        # Verify queue
        client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS).json()
        # Completed count should be 0 (at least for our test job)
        assert redis.get("rrag:job:test-av-1") is None
        assert redis.get("rrag:job:test-av-2") is not None
        assert redis.get("rrag:job:test-av-3") is not None

        # Cleanup
        for jid in ("test-av-2", "test-av-3"):
            redis.delete(f"rrag:job:{jid}")


# -- Test 9: Health Endpoint Availability --------------------------------------


class TestHealthEndpoint:
    def test_main_health_endpoint(self, client):
        """The main /health endpoint should work."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_admin_health_vs_main_health(self, client):
        """Admin health should be more detailed than main health."""
        main_health = client.get("/health").json()
        admin_health = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS).json()

        assert "services" in admin_health  # Admin has service breakdown
        assert "services" not in main_health  # Main doesn't


# -- Test 10: Error Resilience -------------------------------------------------


class TestAdminErrorResilience:
    def test_stats_endpoint_doesnt_crash(self, client):
        """Stats endpoint should handle missing data gracefully."""
        resp = client.get("/api/v1/ingestion/admin/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    def test_queue_stats_empty_system(self, client):
        """Queue stats should work on empty system."""
        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalJobs"] >= 0

    def test_timeline_empty_system(self, client):
        """Timeline should work on empty system."""
        resp = client.get("/api/v1/ingestion/admin/queue/timeline", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert isinstance(resp.json()["timeline"], list)

    def test_health_returns_even_with_down_services(self, client):
        """Health check should return results even if some services are down."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        # Even if auth/pipeline services are down, we should get a response
        data = resp.json()
        assert len(data["services"]) >= 1


# -- Test 11: Config Validation ------------------------------------------------


class TestConfigValidation:
    """Tests verifying input validation on config update endpoint."""

    def test_negative_job_timeout_rejected(self, client):
        """Negative rqJobTimeout should be rejected with 422."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "rqJobTimeout": -100,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 422
        assert "positive" in resp.json()["detail"].lower()

    def test_zero_job_timeout_rejected(self, client):
        """Zero rqJobTimeout should be rejected with 422."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "rqJobTimeout": 0,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 422

    def test_negative_upload_size_rejected(self, client):
        """Negative maxUploadSizeMb should be rejected with 422."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "maxUploadSizeMb": -50,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 422

    def test_empty_model_name_rejected(self, client):
        """Empty string model name should be rejected with 422."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "defaultLlmModel": "   ",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 422
        assert "empty" in resp.json()["detail"].lower()

    def test_valid_positive_timeout_accepted(self, client):
        """Valid positive rqJobTimeout should be accepted."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "rqJobTimeout": 1800,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["updated"]["rqJobTimeout"] == 1800

        # Restore
        client.put("/api/v1/ingestion/admin/config", json={"rqJobTimeout": 3600}, headers=ADMIN_HEADERS)

    def test_multiple_validation_errors(self, client):
        """Multiple invalid values should all be reported."""
        resp = client.put("/api/v1/ingestion/admin/config", json={
            "rqJobTimeout": -1,
            "maxUploadSizeMb": -5,
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "rqJobTimeout" in detail
        assert "maxUploadSizeMb" in detail


# -- Test 12: Health Check Service Names ---------------------------------------


class TestHealthCheckServiceNames:
    """Tests that health check properly names services even on errors."""

    def test_all_services_have_real_names(self, client):
        """No service should have name 'Unknown' even if down."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        data = resp.json()
        for service in data["services"]:
            assert service["name"] != "Unknown", (
                f"Service at URL '{service['url']}' should not have name 'Unknown'"
            )

    def test_expected_service_names_present(self, client):
        """Expected service names should be in the response."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        data = resp.json()
        names = {s["name"] for s in data["services"]}
        assert "Redis" in names
        assert "Ingestion Service" in names
        assert "Pipeline Service" in names
        assert "Auth Server" in names

    def test_down_services_retain_url(self, client):
        """Down services should still have their URL, not empty string."""
        resp = client.get("/api/v1/ingestion/admin/health", headers=ADMIN_HEADERS)
        data = resp.json()
        for service in data["services"]:
            if service["status"] == "down":
                assert service["url"], f"Service '{service['name']}' has empty URL"


# -- Test 13: Boundary & Edge Cases --------------------------------------------


class TestBoundaryEdgeCases:
    """Tests for boundary conditions and edge cases."""

    def test_timeline_zero_hours(self, client):
        """Timeline with 0 hours should return empty."""
        resp = client.get("/api/v1/ingestion/admin/queue/timeline", params={"hours": 0}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["hours"] == 0

    def test_timeline_large_hours(self, client):
        """Timeline with large hours value should not crash."""
        resp = client.get("/api/v1/ingestion/admin/queue/timeline", params={"hours": 8760}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    def test_queue_action_with_no_matching_jobs(self, client):
        """Purge action when no jobs match should return affected=0."""
        # Ensure no failed jobs
        redis = app.state.redis
        for key in redis.scan_iter(match="rrag:job:test-*", count=200):
            redis.delete(key)

        resp = client.post("/api/v1/ingestion/admin/queue/actions", json={
            "action": "purge_failed",
        }, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        # affected could be 0 or more depending on pre-existing data
        assert resp.json()["affected"] >= 0

    def test_malformed_job_data_doesnt_crash_stats(self, client):
        """Stats should handle malformed job data in Redis gracefully."""
        redis = app.state.redis
        # Write a job with minimal/missing fields
        redis.set("rrag:job:test-malformed", json.dumps({
            "id": "test-malformed",
            "status": "completed",
        }), ex=60)

        resp = client.get("/api/v1/ingestion/admin/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

        redis.delete("rrag:job:test-malformed")

    def test_queue_stats_oldest_queued_age_is_positive(self, client):
        """Oldest queued age should be a positive number when queued jobs exist."""
        _create_test_job(client, "test-oqa-1", "queued")

        resp = client.get("/api/v1/ingestion/admin/queue/stats", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["oldestQueuedAge"] is not None
        assert data["oldestQueuedAge"] >= 0

        redis.delete("rrag:job:test-oqa-1")
