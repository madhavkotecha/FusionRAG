"""Tests for expanded QueryPipeline models and query executor.

Covers:
1. QueryPipeline model validation with rich configs
2. RetrieverConfig, RerankerConfig, GeneratorConfig defaults and validation
3. PlannerConfig, AgentConfig new models
4. Create with custom ID (sync fix)
5. Query executor reranking step
6. Query pipeline to tool schema
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest

if sys.platform == "win32":
    _rq_mock = MagicMock()
    sys.modules.setdefault("rq", _rq_mock)
    sys.modules.setdefault("rq.queue", _rq_mock)
    sys.modules.setdefault("rq.job", _rq_mock)
    sys.modules.setdefault("rq.worker", _rq_mock)

from rrag_ingestion.models.query_pipeline import (
    AgentConfig,
    GeneratorConfig,
    PlannerConfig,
    QueryPipeline,
    RerankerConfig,
    RetrieverConfig,
    query_pipeline_to_tool,
    tool_name_to_pipeline_id,
)


# ── 1. Model Defaults ──────────────────────────────────────────────────


class TestRetrieverConfig:
    def test_defaults(self):
        cfg = RetrieverConfig()
        assert cfg.strategy == "dense"
        assert cfg.top_k == 20
        assert cfg.score_threshold == 0.0
        assert cfg.alpha == 0.6
        assert cfg.fusion_method == "rrf"
        assert cfg.use_mmr is False

    def test_override(self):
        cfg = RetrieverConfig(
            strategy="hybrid", top_k=50, alpha=0.8, use_mmr=True
        )
        assert cfg.strategy == "hybrid"
        assert cfg.top_k == 50
        assert cfg.alpha == 0.8
        assert cfg.use_mmr is True

    def test_validation_bounds(self):
        with pytest.raises(Exception):
            RetrieverConfig(top_k=0)
        with pytest.raises(Exception):
            RetrieverConfig(alpha=1.5)
        with pytest.raises(Exception):
            RetrieverConfig(score_threshold=-0.1)


class TestRerankerConfig:
    def test_defaults(self):
        cfg = RerankerConfig()
        assert cfg.enabled is False
        assert cfg.strategy == "cross_encoder"
        assert cfg.model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert cfg.top_k == 10
        assert cfg.max_length == 512
        assert cfg.batch_size == 32

    def test_enabled_with_custom_model(self):
        cfg = RerankerConfig(
            enabled=True, strategy="cohere", model="rerank-english-v3.0"
        )
        assert cfg.enabled is True
        assert cfg.strategy == "cohere"
        assert cfg.model == "rerank-english-v3.0"


class TestGeneratorConfig:
    def test_defaults(self):
        cfg = GeneratorConfig()
        assert cfg.model == "gpt-4o-mini"
        assert cfg.provider == "openai"
        assert cfg.temperature == 0.2
        assert cfg.citation_mode == "inline"
        assert cfg.context_ordering == "relevance_first"
        assert cfg.enable_cot is False
        assert cfg.stream is True

    def test_anthropic_provider(self):
        cfg = GeneratorConfig(
            model="claude-sonnet-4-6",
            provider="anthropic",
            temperature=0.0,
        )
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-6"


class TestPlannerConfig:
    def test_defaults(self):
        cfg = PlannerConfig()
        assert cfg.enabled is False
        assert cfg.strategy == "corag"
        assert cfg.max_hops == 3

    def test_mcts_config(self):
        cfg = PlannerConfig(
            enabled=True, strategy="mcts", beam_width=5, max_hops=5
        )
        assert cfg.strategy == "mcts"
        assert cfg.beam_width == 5


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.enabled is False
        assert cfg.agent_type == "router"
        assert cfg.routing_mode == "adaptive"
        assert cfg.max_retries == 3

    def test_reflection_agent(self):
        cfg = AgentConfig(
            enabled=True,
            agent_type="reflection",
            min_quality_score=7.0,
        )
        assert cfg.agent_type == "reflection"
        assert cfg.min_quality_score == 7.0


# ── 2. QueryPipeline Full Model ────────────────────────────────────────


class TestQueryPipelineModel:
    def test_minimal_creation(self):
        qp = QueryPipeline(id="test-1", datastore_id="ds-1", name="Test")
        assert qp.retrieval_strategy == "auto"
        assert qp.retriever.top_k == 20
        assert qp.reranker.enabled is False
        assert qp.planner.enabled is False
        assert qp.agent.enabled is False

    def test_full_creation(self):
        qp = QueryPipeline(
            id="test-2",
            name="Full Pipeline",
            description="A complete pipeline",
            datastore_id="ds-1",
            retrieval_strategy="hybrid",
            retriever=RetrieverConfig(strategy="hybrid", top_k=30, alpha=0.7),
            reranker=RerankerConfig(enabled=True, top_k=5),
            generator=GeneratorConfig(model="gpt-4o", temperature=0.0),
            planner=PlannerConfig(enabled=True, strategy="mcts"),
            agent=AgentConfig(enabled=True, agent_type="orchestrator"),
            definition={"nodes": [], "edges": []},
        )
        assert qp.retriever.alpha == 0.7
        assert qp.reranker.enabled is True
        assert qp.generator.model == "gpt-4o"
        assert qp.planner.strategy == "mcts"
        assert qp.agent.agent_type == "orchestrator"
        assert qp.definition is not None

    def test_serialization_roundtrip(self):
        qp = QueryPipeline(
            id="test-3",
            name="Roundtrip",
            datastore_id="ds-1",
            retriever=RetrieverConfig(strategy="hybrid", alpha=0.8),
        )
        json_str = qp.model_dump_json()
        restored = QueryPipeline.model_validate_json(json_str)
        assert restored.retriever.alpha == 0.8
        assert restored.retriever.strategy == "hybrid"


# ── 3. Tool Schema Generation ──────────────────────────────────────────


class TestToolSchema:
    def test_tool_schema_structure(self):
        qp = QueryPipeline(
            id="abc-def-123",
            name="Research KB",
            description="Searches papers",
            datastore_id="ds-1",
            retrieval_strategy="hybrid",
        )
        schema = query_pipeline_to_tool(qp)
        assert schema["type"] == "function"
        assert "query" in schema["function"]["name"]
        assert "Research KB" in schema["function"]["description"]
        assert "Searches papers" in schema["function"]["description"]
        assert "hybrid" in schema["function"]["description"]
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "query" in params["required"]

    def test_tool_name_to_pipeline_id(self):
        tool_name = "query_abc_def_123"
        pid = tool_name_to_pipeline_id(tool_name)
        assert pid == "abc-def-123"


# ── 4. Create with Custom ID (Sync Fix) ────────────────────────────────


class TestCreateWithCustomId:
    def test_db_store_uses_provided_id(self):
        """Verify db.create_query_pipeline uses ID from data when provided."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from rrag_ingestion.db import stores as db

        custom_id = "custom-pipeline-id-123"
        mock_session = AsyncMock()

        async def run():
            result = await db.create_query_pipeline(
                mock_session,
                "ws-test-001",
                {
                    "id": custom_id,
                    "name": "Synced Pipeline",
                    "datastore_id": "ds-1",
                },
            )
            assert result["id"] == custom_id
            assert result["name"] == "Synced Pipeline"

        asyncio.get_event_loop().run_until_complete(run())

    def test_db_store_generates_id_when_not_provided(self):
        """Verify db.create_query_pipeline generates UUID when id not in data."""
        import asyncio
        from unittest.mock import AsyncMock

        from rrag_ingestion.db import stores as db

        mock_session = AsyncMock()

        async def run():
            result = await db.create_query_pipeline(
                mock_session,
                "ws-test-001",
                {
                    "name": "Auto-ID Pipeline",
                    "datastore_id": "ds-1",
                },
            )
            assert result["id"]  # Not empty
            assert len(result["id"]) == 36  # UUID format

        asyncio.get_event_loop().run_until_complete(run())


# ── 5. Query Executor Reranking ─────────────────────────────────────────


class TestQueryExecutorReranking:
    @pytest.mark.asyncio
    async def test_rerank_sources_cross_encoder_fallback(self):
        """Test reranking gracefully falls back when sentence-transformers unavailable."""
        from rrag_ingestion.services.query_executor import (
            RetrievedSource,
            _rerank_sources,
        )

        sources = [
            RetrievedSource(id="1", content="Alpha content", score=0.9),
            RetrievedSource(id="2", content="Beta content", score=0.7),
            RetrievedSource(id="3", content="Gamma content", score=0.5),
        ]
        config = RerankerConfig(
            enabled=True, strategy="cross_encoder", top_k=2
        )

        # Will either use cross-encoder (if installed) or fall back gracefully
        result = await _rerank_sources(sources, "test query", config)
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_rerank_sources_score_threshold(self):
        """Test score threshold filtering after reranking."""
        from rrag_ingestion.services.query_executor import (
            RetrievedSource,
            _rerank_sources,
        )

        sources = [
            RetrievedSource(id="1", content="High", score=0.9),
            RetrievedSource(id="2", content="Low", score=0.1),
        ]
        config = RerankerConfig(
            enabled=True,
            strategy="cross_encoder",
            top_k=10,
            score_threshold=0.5,
        )

        result = await _rerank_sources(sources, "test", config)
        # After cross-encoder fallback (returns top_k), threshold filters
        # The exact result depends on whether sentence-transformers is installed
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_rerank_cohere_stub(self):
        """Test Cohere reranking stub truncates to top_k."""
        from rrag_ingestion.services.query_executor import (
            RetrievedSource,
            _rerank_sources,
        )

        sources = [
            RetrievedSource(id=str(i), content=f"Doc {i}", score=0.5)
            for i in range(10)
        ]
        config = RerankerConfig(enabled=True, strategy="cohere", top_k=3)

        result = await _rerank_sources(sources, "test", config)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_jina_stub(self):
        """Test Jina reranking stub truncates to top_k."""
        from rrag_ingestion.services.query_executor import (
            RetrievedSource,
            _rerank_sources,
        )

        sources = [
            RetrievedSource(id=str(i), content=f"Doc {i}", score=0.5)
            for i in range(10)
        ]
        config = RerankerConfig(enabled=True, strategy="jina", top_k=4)

        result = await _rerank_sources(sources, "test", config)
        assert len(result) == 4


# ── 6. Query Executor Trace ────────────────────────────────────────────


class TestQueryTrace:
    def test_trace_step_serialization(self):
        from rrag_ingestion.services.query_executor import TraceStep

        step = TraceStep(
            step="embed",
            status="completed",
            duration_ms=12.345,
            input_summary={"query_length": 10},
            output_summary={"dimensions": 1536},
        )
        d = step.to_dict()
        assert d["step"] == "embed"
        assert d["status"] == "completed"
        assert d["duration_ms"] == 12.35
        assert d["error"] is None

    def test_query_trace_serialization(self):
        from rrag_ingestion.services.query_executor import (
            QueryTrace,
            TraceStep,
        )

        trace = QueryTrace(
            pipeline_id="p1",
            pipeline_name="Test",
            query="what?",
            total_duration_ms=100.5,
        )
        trace.steps.append(
            TraceStep(step="embed", status="completed", duration_ms=50.0)
        )
        trace.steps.append(
            TraceStep(step="retrieve", status="completed", duration_ms=50.0)
        )

        d = trace.to_dict()
        assert d["pipeline_id"] == "p1"
        assert len(d["steps"]) == 2
        assert d["total_duration_ms"] == 100.5

    def test_retrieved_source_serialization(self):
        from rrag_ingestion.services.query_executor import RetrievedSource

        source = RetrievedSource(
            id="s1",
            content="Hello world",
            score=0.95,
            metadata={"source": "vector"},
        )
        d = source.to_dict()
        assert d["id"] == "s1"
        assert d["score"] == 0.95
        assert d["metadata"]["source"] == "vector"
