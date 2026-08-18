"""End-to-end tests for the query pipeline + chat system.

Verifies:
1. Query pipeline CRUD
2. Chat requires query pipelines (no direct datastore access)
3. Tool schema auto-generation
4. Chat with tool-calling (mocked LLM)
5. Streaming SSE events
6. Full trace in responses
"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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

# ── Auth constants ────────────────────────────────────────────────────
TEST_WORKSPACE_ID = "ws-test-001"

AUTH_HEADERS = {
    "X-Auth-User-Id": "test-user-001",
    "X-Auth-Org-Id": "test-org-001",
    "X-Auth-Org-Role": "member",
    "X-Auth-Email": "test@example.com",
    "X-Auth-Workspace-Roles": json.dumps({TEST_WORKSPACE_ID: "developer"}),
}

WS_PARAMS = {"workspace_id": TEST_WORKSPACE_ID}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_redis(client):
    """Ensure Redis state is clean for each test."""
    redis = app.state.redis
    for key in redis.scan_iter(match="rrag:query_pipeline:*", count=200):
        redis.delete(key)
    for key in redis.scan_iter(match="rrag:datastore:*test-ds-*", count=200):
        redis.delete(key)
    for key in redis.scan_iter(match="rrag:conv:*", count=200):
        redis.delete(key)
    yield
    for key in redis.scan_iter(match="rrag:query_pipeline:*", count=200):
        redis.delete(key)
    for key in redis.scan_iter(match="rrag:datastore:*test-ds-*", count=200):
        redis.delete(key)
    for key in redis.scan_iter(match="rrag:conv:*", count=200):
        redis.delete(key)


@pytest.fixture
def datastore(client):
    """Create a test datastore in Redis (workspace-scoped key)."""
    redis = app.state.redis
    ds_id = "test-ds-e2e"
    ds_data = json.dumps({
        "id": ds_id,
        "name": "Test DataStore",
        "description": "E2E test datastore",
        "pipeline_name": "test",
        "source_document_ids": [],
        "created_by_job_id": "",
        "status": "ready",
        "targets": [
            {
                "type": "vector",
                "backend": "faiss",
                "config": {"index_path": "./data/test_index"},
                "stats": {},
            }
        ],
        "created_at": "2024-01-01T00:00:00",
        "updated_at": None,
    })
    redis.set(f"rrag:datastore:{TEST_WORKSPACE_ID}:{ds_id}", ds_data)
    return ds_id


# ── Test 1: Query Pipeline CRUD ────────────────────────────────────────


class TestQueryPipelineCRUD:
    def test_create_query_pipeline(self, client, datastore):
        resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Test QP",
                "description": "A test query pipeline",
                "datastore_id": datastore,
                "retrieval_strategy": "vector",
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test QP"
        assert data["datastore_id"] == datastore
        assert data["retrieval_strategy"] == "vector"
        assert data["id"]
        assert data["created_at"]

    def test_list_query_pipelines(self, client, datastore):
        client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "QP1", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "QP2", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )

        resp = client.get(
            "/api/v1/ingestion/query-pipelines",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["query_pipelines"]) >= 2

    def test_get_query_pipeline(self, client, datastore):
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Get Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get(
            "/api/v1/ingestion/query-pipelines/nonexistent",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 404

    def test_update_query_pipeline(self, client, datastore):
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Before", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/ingestion/query-pipelines/{qp_id}",
            json={"name": "After", "retrieval_strategy": "hybrid"},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "After"
        assert resp.json()["retrieval_strategy"] == "hybrid"
        assert resp.json()["updated_at"] is not None

    def test_delete_query_pipeline(self, client, datastore):
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Delete Me", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        resp = client.delete(
            f"/api/v1/ingestion/query-pipelines/{qp_id}",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 404


# ── Test 2: Tool Schema Auto-Generation ──────────────────────────────


class TestToolSchema:
    def test_tool_schema_generated(self, client, datastore):
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Research Pipeline",
                "description": "Searches research papers",
                "datastore_id": datastore,
                "retrieval_strategy": "hybrid",
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200
        schema = resp.json()

        assert schema["type"] == "function"
        assert "query" in schema["function"]["name"]
        assert "Research Pipeline" in schema["function"]["description"]
        assert "Searches research papers" in schema["function"]["description"]
        params = schema["function"]["parameters"]
        assert "query" in params["properties"]
        assert "query" in params["required"]


# ── Test 3: No Direct DataStore Chat ──────────────────────────────────


class TestNoDirectDatastoreAccess:
    def test_old_query_endpoint_removed(self, client):
        """The old /api/v1/ingestion/query endpoint should not exist as a standalone route."""
        resp = client.post("/api/v1/ingestion/query", json={
            "query": "test", "datastore_id": "some-id",
        })
        # 404 = route not mounted, 401 = route exists but requires auth
        assert resp.status_code in (404, 401, 405)

    def test_chat_requires_pipeline_ids(self, client):
        """Chat endpoint should reject requests without pipeline IDs."""
        resp = client.post(
            "/api/v1/ingestion/chat",
            json={"message": "hello"},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 422

    def test_chat_rejects_empty_pipelines(self, client):
        """Chat endpoint should reject empty pipeline list."""
        resp = client.post(
            "/api/v1/ingestion/chat",
            json={"message": "hello", "query_pipeline_ids": []},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 422

    def test_chat_rejects_invalid_pipelines(self, client):
        """Chat endpoint should reject invalid pipeline IDs."""
        resp = client.post(
            "/api/v1/ingestion/chat",
            json={"message": "hello", "query_pipeline_ids": ["nonexistent-id"]},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 400


# ── Test 4: Chat With Tool-Calling (mocked LLM) ──────────────────────


def _make_mock_tool_call_response(tool_name: str, query: str, tool_call_id: str = "tc_1"):
    """Create a mock LLM response that contains a tool call."""
    msg = MagicMock()
    tc = MagicMock()
    tc.id = tool_call_id
    tc.function.name = tool_name
    tc.function.arguments = json.dumps({"query": query})
    msg.tool_calls = [tc]
    msg.content = None
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps({"query": query})},
        }],
    }

    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    resp.usage = MagicMock(total_tokens=100)
    return resp


def _make_mock_text_response(text: str):
    """Create a mock LLM response with text content."""
    msg = MagicMock()
    msg.tool_calls = None
    msg.content = text
    msg.model_dump.return_value = {"role": "assistant", "content": text}

    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    resp.usage = MagicMock(total_tokens=150)
    return resp


class TestChatWithToolCalling:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_chat_executes_tool_and_returns_trace(
        self, mock_completion, mock_embedding, client, datastore
    ):
        """Full E2E: create pipeline -> chat -> verify tool call + trace."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "E2E Test Pipeline",
                "description": "Tests end-to-end",
                "datastore_id": datastore,
                "retrieval_strategy": "vector",
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert create_resp.status_code == 201
        qp = create_resp.json()
        qp_id = qp["id"]

        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]

        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "what is AI?"),
            _make_mock_text_response("AI is artificial intelligence. [Document 1]"),
        ]

        resp = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "What is AI?",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )

        assert resp.status_code == 200
        data = resp.json()

        assert data["answer"] == "AI is artificial intelligence. [Document 1]"
        assert data["conversation_id"]
        assert data["model"] == "gpt-4o-mini"
        assert data["tokens_used"] > 0
        assert data["duration_ms"] > 0

        # Verify traces
        assert len(data["traces"]) >= 1
        trace = data["traces"][0]
        assert trace["pipeline_id"] == qp_id
        assert trace["pipeline_name"] == "E2E Test Pipeline"
        assert trace["query"] == "what is AI?"
        assert len(trace["steps"]) >= 2  # embed + retrieve
        assert trace["total_duration_ms"] > 0

        step_names = [s["step"] for s in trace["steps"]]
        assert "embed" in step_names
        assert "retrieve" in step_names

        for step in trace["steps"]:
            assert "duration_ms" in step
            assert "status" in step

        # Verify LLM was called with tools
        assert mock_completion.call_count == 2
        first_call_kwargs = mock_completion.call_args_list[0].kwargs
        assert first_call_kwargs.get("tools") is not None


# ── Test 5: Streaming SSE Events ──────────────────────────────────────


class TestStreaming:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.stream_completion")
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_stream_chat_returns_sse_events(
        self, mock_completion, mock_stream, mock_embedding, client, datastore
    ):
        """Verify SSE stream contains start, trace, token, done events."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Stream Test",
                "datastore_id": datastore,
                "retrieval_strategy": "vector",
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp = create_resp.json()
        qp_id = qp["id"]

        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]

        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "test query"),
            _make_mock_text_response("Fallback"),
        ]

        async def mock_stream_gen(*args, **kwargs):
            for token in ["The ", "answer ", "is ", "42."]:
                chunk = MagicMock()
                chunk.choices = [MagicMock(delta=MagicMock(content=token))]
                yield chunk

        mock_stream.return_value = mock_stream_gen()

        with client.stream(
            "POST",
            "/api/v1/ingestion/chat/stream",
            json={
                "message": "What is the answer?",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        ) as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass

        event_types = [e["type"] for e in events]
        assert "start" in event_types, f"Expected 'start' event, got: {event_types}"
        assert "trace" in event_types, f"Expected 'trace' event, got: {event_types}"

        start_evt = next(e for e in events if e["type"] == "start")
        assert "id" in start_evt
        assert "conversation_id" in start_evt

        trace_evt = next(e for e in events if e["type"] == "trace")
        assert "trace" in trace_evt
        assert trace_evt["trace"]["pipeline_name"] == "Stream Test"
        assert len(trace_evt["trace"]["steps"]) >= 2


# ── Test 6: Conversation Management ──────────────────────────────────


class TestConversationManagement:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_conversation_persists(self, mock_completion, mock_embedding, client, datastore):
        """Verify conversation history is maintained across messages."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Conv Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]
        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "first"),
            _make_mock_text_response("Answer 1"),
        ]

        resp1 = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "First question",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        conv_id = resp1.json()["conversation_id"]

        conv_resp = client.get(
            f"/api/v1/ingestion/chat/conversations/{conv_id}",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert conv_resp.status_code == 200
        msgs = conv_resp.json()["messages"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_delete_conversation(self, client):
        resp = client.delete(
            "/api/v1/ingestion/chat/conversations/some-id",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


# ── Test 7: Generator Config Applied ──────────────────────────────────


class TestGeneratorConfig:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_generator_system_prompt_used(
        self, mock_completion, mock_embedding, client, datastore
    ):
        """Verify the pipeline's generator.system_prompt is sent to the LLM."""
        custom_prompt = "You are a specialized legal assistant. Only answer legal questions."
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Legal Pipeline",
                "datastore_id": datastore,
                "generator": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "system_prompt": custom_prompt,
                },
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert create_resp.status_code == 201
        qp_id = create_resp.json()["id"]
        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "contract law"),
            _make_mock_text_response("Contract law governs agreements."),
        ]

        client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "What is contract law?",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )

        # Verify the system prompt passed to LLM matches the pipeline config
        first_call = mock_completion.call_args_list[0]
        messages = first_call.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == custom_prompt

    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_generator_model_used_as_default(
        self, mock_completion, mock_embedding, client, datastore
    ):
        """Verify the pipeline's generator.model is used when ChatRequest uses default."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Custom Model Pipeline",
                "datastore_id": datastore,
                "generator": {"model": "gpt-4o"},
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]
        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "test"),
            _make_mock_text_response("Result"),
        ]

        # Use default model (gpt-4o-mini) - should be overridden by pipeline's gpt-4o
        resp = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "Test",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 200

        first_call = mock_completion.call_args_list[0]
        assert first_call.kwargs["model"] == "gpt-4o"


# ── Test 8: Context Template ─────────────────────────────────────────


class TestContextTemplate:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.query_executor._retrieve_from_faiss")
    def test_custom_context_template_applied(
        self, mock_faiss, mock_completion, mock_embedding, client, datastore
    ):
        """Verify generator.context_template formats the tool results."""
        from rrag_ingestion.services.query_executor import RetrievedSource

        custom_template = "### Source {index} (relevance: {score})\n{content}"
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Template Pipeline",
                "datastore_id": datastore,
                "retrieval_strategy": "vector",
                "generator": {"context_template": custom_template},
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]
        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]
        mock_faiss.return_value = [
            RetrievedSource(id="doc1", content="Test document content", score=0.95),
        ]

        captured_tool_results = []

        def capture_completion(**kwargs):
            messages = kwargs.get("messages", [])
            for m in messages:
                if m.get("role") == "tool":
                    captured_tool_results.append(m["content"])
            if not captured_tool_results:
                return _make_mock_tool_call_response(tool_name, "test query")
            return _make_mock_text_response("Done")

        mock_completion.side_effect = capture_completion

        client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "Test",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )

        assert len(captured_tool_results) >= 1
        assert "### Source 1" in captured_tool_results[0]
        assert "relevance: 0.950" in captured_tool_results[0]
        assert "Test document content" in captured_tool_results[0]


# ── Test 9: Pipeline Validation ──────────────────────────────────────


class TestPipelineValidation:
    def test_create_requires_name(self, client, datastore):
        resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 422

    def test_create_requires_datastore_id(self, client):
        resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Test"},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 422

    def test_create_with_custom_retriever(self, client, datastore):
        resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Custom Retriever",
                "datastore_id": datastore,
                "retriever": {"strategy": "hybrid", "top_k": 50, "alpha": 0.8},
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["retriever"]["strategy"] == "hybrid"
        assert data["retriever"]["top_k"] == 50
        assert data["retriever"]["alpha"] == 0.8

    def test_create_with_reranker(self, client, datastore):
        resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "With Reranker",
                "datastore_id": datastore,
                "reranker": {"enabled": True, "strategy": "cross_encoder", "top_k": 5},
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["reranker"]["enabled"] is True
        assert data["reranker"]["strategy"] == "cross_encoder"
        assert data["reranker"]["top_k"] == 5

    def test_create_with_planner_and_agent(self, client, datastore):
        resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={
                "name": "Full Config",
                "datastore_id": datastore,
                "planner": {"enabled": True, "strategy": "ircot", "max_hops": 5},
                "agent": {"enabled": True, "agent_type": "reflection", "max_retries": 2},
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["planner"]["enabled"] is True
        assert data["planner"]["strategy"] == "ircot"
        assert data["agent"]["enabled"] is True
        assert data["agent"]["agent_type"] == "reflection"


# ── Test 10: Streaming Token Events ──────────────────────────────────


class TestStreamingTokens:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.stream_completion")
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_stream_delivers_tokens_and_done(
        self, mock_completion, mock_stream, mock_embedding, client, datastore
    ):
        """Verify streaming delivers token events and a done event.

        When the non-streaming completion returns content, the optimization
        emits it directly instead of making a redundant streaming call.
        """
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Token Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]
        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]
        # First call returns tool call, second returns the final text answer
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "streaming test"),
            _make_mock_text_response("The answer based on context."),
        ]

        with client.stream(
            "POST",
            "/api/v1/ingestion/chat/stream",
            json={
                "message": "Say hello",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        ) as response:
            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass

        event_types = [e["type"] for e in events]
        assert "token" in event_types, f"Expected 'token' events, got: {event_types}"
        assert "done" in event_types, f"Expected 'done' event, got: {event_types}"

        # The answer is emitted from the non-streaming completion (optimization)
        token_events = [e for e in events if e["type"] == "token"]
        streamed_text = "".join(e["content"] for e in token_events)
        assert streamed_text == "The answer based on context."

        # Verify done event has complete answer
        done_evt = next(e for e in events if e["type"] == "done")
        assert done_evt["answer"] == "The answer based on context."


# ── Test 11: Multi-Round Tool Calling ──────────────────────────────────


class TestMultiRoundToolCalling:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_two_rounds_of_tool_calls(
        self, mock_completion, mock_embedding, client, datastore
    ):
        """Verify the chat loop handles multiple rounds of tool calls correctly."""
        # Create two pipelines so LLM can call both
        resp1 = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Pipeline A", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        resp2 = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Pipeline B", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp1_id = resp1.json()["id"]
        qp2_id = resp2.json()["id"]

        tool1 = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp1_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        ).json()
        tool2 = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp2_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        ).json()
        tool1_name = tool1["function"]["name"]
        tool2_name = tool2["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]

        # Round 1: LLM calls pipeline A
        # Round 2: LLM calls pipeline B
        # Round 3: LLM returns final text
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool1_name, "first query", "tc_1"),
            _make_mock_tool_call_response(tool2_name, "second query", "tc_2"),
            _make_mock_text_response("Combined answer from both pipelines."),
        ]

        resp = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "Compare results from both sources",
                "query_pipeline_ids": [qp1_id, qp2_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Combined answer from both pipelines."
        assert len(data["traces"]) == 2  # Two tool calls = two traces
        assert mock_completion.call_count == 3  # 2 tool calls + 1 final


# ── Test 12: Conversation Continuation ──────────────────────────────────


class TestConversationContinuation:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_second_message_includes_history(
        self, mock_completion, mock_embedding, client, datastore
    ):
        """Verify sending a 2nd message with same conversation_id includes prior history."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "History Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]
        tool_resp = client.get(
            f"/api/v1/ingestion/query-pipelines/{qp_id}/tool-schema",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        tool_name = tool_resp.json()["function"]["name"]

        mock_embedding.return_value = [[0.1] * 1536]

        # First message
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "first"),
            _make_mock_text_response("First answer"),
        ]

        resp1 = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "First question",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp1.status_code == 200
        conv_id = resp1.json()["conversation_id"]

        # Second message reusing conversation_id
        mock_completion.reset_mock()
        mock_completion.side_effect = [
            _make_mock_tool_call_response(tool_name, "second"),
            _make_mock_text_response("Second answer"),
        ]

        resp2 = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "Follow-up question",
                "query_pipeline_ids": [qp_id],
                "conversation_id": conv_id,
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id
        assert resp2.json()["answer"] == "Second answer"

        # Verify LLM received history (system + prior user + prior assistant + new user)
        first_call_messages = mock_completion.call_args_list[0].kwargs["messages"]
        assert first_call_messages[0]["role"] == "system"
        # History should include "First question" and "First answer"
        roles = [m["role"] for m in first_call_messages]
        assert "user" in roles  # At least one prior user message
        msg_contents = [m.get("content", "") for m in first_call_messages]
        assert any("First question" in str(c) for c in msg_contents)
        assert any("First answer" in str(c) for c in msg_contents)

        # Verify conversation now has 4 messages (2 turns)
        conv_resp = client.get(
            f"/api/v1/ingestion/chat/conversations/{conv_id}",
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert len(conv_resp.json()["messages"]) == 4


# ── Test 13: Error Handling ─────────────────────────────────────────────


class TestChatErrorHandling:
    @patch("rrag_ingestion.services.llm_service.embedding", new_callable=AsyncMock)
    @patch("rrag_ingestion.services.llm_service.completion", new_callable=AsyncMock)
    def test_llm_failure_returns_error(
        self, mock_completion, mock_embedding, client, datastore
    ):
        """Verify chat endpoint handles LLM failures gracefully."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Error Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        mock_embedding.return_value = [[0.1] * 1536]
        mock_completion.side_effect = Exception("LLM service unavailable")

        resp = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "This should fail",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 502
        assert "LLM service error" in resp.json()["detail"]

    def test_message_too_long(self, client, datastore):
        """Verify chat rejects messages exceeding max_length."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Length Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        resp = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "x" * 10001,  # Exceeds 10000 limit
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 422

    def test_empty_message_rejected(self, client, datastore):
        """Verify chat rejects empty messages."""
        create_resp = client.post(
            "/api/v1/ingestion/query-pipelines",
            json={"name": "Empty Test", "datastore_id": datastore},
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        qp_id = create_resp.json()["id"]

        resp = client.post(
            "/api/v1/ingestion/chat",
            json={
                "message": "",
                "query_pipeline_ids": [qp_id],
            },
            headers=AUTH_HEADERS,
            params=WS_PARAMS,
        )
        assert resp.status_code == 422
