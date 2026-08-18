from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.pipeline_run import PipelineRun, RunStatus

logger = logging.getLogger(__name__)


def _emit(redis, run_id: str, event: str, data: dict) -> None:
    """Publish an SSE event to Redis pub/sub for real-time streaming."""
    if not redis:
        return
    try:
        payload = {"event": event, **data}
        redis.publish(f"pipeline_run:{run_id}", json.dumps(payload, default=str))
    except Exception as e:
        logger.debug(f"Failed to emit event {event}: {e}")


class CycleDetectedError(Exception):
    """Raised when the pipeline DAG contains a cycle."""


def _topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Return node IDs in topological order based on edges.

    Raises CycleDetectedError if the graph contains a cycle.
    """
    graph: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        graph.setdefault(source, []).append(target)
        in_degree.setdefault(target, 0)
        in_degree[target] += 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for neighbour in graph.get(nid, []):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(graph):
        visited = set(order)
        cycle_nodes = [nid for nid in graph if nid not in visited]
        raise CycleDetectedError(
            f"Pipeline contains a cycle involving nodes: {cycle_nodes}"
        )

    return order


def _get_node_data(node: dict) -> dict:
    """Extract data fields from a node, handling both flat and nested structures."""
    data = node.get("data", {})
    return {
        "label": data.get("label", node.get("label", "")),
        "componentType": data.get("componentType", node.get("type", "")),
        "category": data.get("category", node.get("type", "")),
        "config": data.get("config", node.get("config", {})),
    }


async def _execute_node(
    node: dict,
    input_data: dict[str, Any],
    previous_outputs: dict[str, dict],
    edges: list[dict],
) -> dict[str, Any]:
    """Execute a single node in the pipeline.

    Collects inputs from predecessor nodes and produces output.
    """
    node_data = _get_node_data(node)
    component_type = node_data["componentType"]
    config = node_data["config"]
    label = node_data["label"]
    category = node_data["category"]
    start = time.monotonic()

    # Check for composite component
    is_composite = node.get("is_composite", False) or (
        node.get("data", {}).get("is_composite", False)
    )
    steps = node.get("steps") or node.get("data", {}).get("steps")

    if is_composite and steps:
        output_data = {
            "composite": True,
            "steps_count": len(steps),
            "component_type": component_type,
            "message": f"Composite component {label} with {len(steps)} steps",
        }
        duration = (time.monotonic() - start) * 1000
        return {
            "node_id": node["id"],
            "node_type": component_type,
            "label": label,
            "category": category,
            "status": "completed",
            "is_composite": True,
            "steps": steps,
            "output_data": output_data,
            "duration_ms": round(duration, 2),
            "message": f"Executed composite {label}",
        }

    # Collect input from predecessor nodes
    node_input = dict(input_data)
    for edge in edges:
        if edge["target"] == node["id"] and edge["source"] in previous_outputs:
            prev = previous_outputs[edge["source"]]
            if isinstance(prev.get("output_data"), dict):
                node_input.update(prev["output_data"])

    # Simulate meaningful execution based on component type
    output_data = {}
    status = "completed"
    message = ""

    try:
        if category in ("parser", "data_source") or component_type in ("file_loader", "multi_parser", "web_scraper"):
            file_path = config.get("file_path", "")
            formats = config.get("formats", ["pdf", "txt"])
            output_data = {
                "documents": [{"id": f"doc_{i}", "content": f"Document {i} content from {file_path}", "metadata": {"source": file_path}} for i in range(1, 4)],
                "document_count": 3,
            }
            message = f"Parsed 3 documents from {file_path or 'input'} ({', '.join(formats) if isinstance(formats, list) else 'auto'})"

        elif category == "chunker" or component_type in ("recursive_chunker", "semantic_chunker", "token_chunker", "sentence_chunker"):
            chunk_size = config.get("chunk_size", config.get("chunk_token_size", 512))
            doc_count = len(node_input.get("documents", [1, 2, 3]))
            chunk_count = doc_count * 5  # ~5 chunks per doc
            output_data = {
                "chunks": [{"id": f"chunk_{i}", "content": f"Chunk {i} text segment", "metadata": {"chunk_index": i}} for i in range(chunk_count)],
                "chunk_count": chunk_count,
            }
            message = f"Created {chunk_count} chunks (size={chunk_size})"

        elif category == "embedder" or component_type in ("openai_embedder", "sentence_transformer_embedder", "e5_embedder"):
            model = config.get("model", config.get("model_name", "text-embedding-3-small"))
            chunks = node_input.get("chunks", [{"id": f"c{i}"} for i in range(15)])
            output_data = {
                "embeddings": [{"id": c.get("id", f"emb_{i}"), "vector": [0.0] * 8, "dimension": 1536} for i, c in enumerate(chunks)],
                "embedding_count": len(chunks),
                "model": model,
            }
            message = f"Generated {len(chunks)} embeddings using {model}"

        elif category == "extractor" or component_type in ("schema_free_extractor", "schema_constrained_extractor", "entity_extractor", "subquery_decomposer"):
            llm_model = config.get("llm_model", "gpt-4o-mini")
            if "subquery" in component_type:
                output_data = {
                    "subqueries": ["What is X?", "How does Y relate to Z?", "What are the key factors?"],
                    "subquery_count": 3,
                }
                message = f"Decomposed into 3 sub-queries using {llm_model}"
            else:
                output_data = {
                    "entities": [
                        {"name": "Entity A", "type": "Organization", "description": "A key organization"},
                        {"name": "Entity B", "type": "Person", "description": "A relevant person"},
                    ],
                    "relations": [
                        {"source": "Entity A", "target": "Entity B", "type": "employs"},
                    ],
                    "entity_count": 2,
                    "relation_count": 1,
                }
                message = f"Extracted 2 entities, 1 relation using {llm_model}"

        elif category == "graph_builder" or component_type in ("lightrag_graph_builder", "kag_subgraph_builder"):
            entities = node_input.get("entities", [])
            output_data = {
                "graph": {"nodes": len(entities) if entities else 5, "edges": max(len(entities) - 1, 3) if entities else 3},
                "graph_stats": {"total_nodes": 5, "total_edges": 3},
            }
            message = f"Built knowledge graph with {output_data['graph']['nodes']} nodes, {output_data['graph']['edges']} edges"

        elif category == "indexer" or component_type in ("faiss_indexer", "milvus_indexer"):
            index_path = config.get("index_path", "./data/index")
            emb_count = node_input.get("embedding_count", 15)
            output_data = {
                "index_path": index_path,
                "indexed_count": emb_count,
            }
            message = f"Indexed {emb_count} vectors at {index_path}"

        elif category == "retriever" or component_type in ("dense_retriever", "hybrid_retriever", "web_retriever"):
            top_k = config.get("top_k", config.get("max_results", 10))
            output_data = {
                "retrieved": [{"id": f"ret_{i}", "content": f"Retrieved document {i}", "score": round(0.95 - i * 0.05, 3)} for i in range(min(top_k, 5))],
                "retrieval_count": min(top_k, 5),
            }
            message = f"Retrieved {min(top_k, 5)} documents (top_k={top_k})"

        elif category == "reranker" or component_type in ("cross_encoder_reranker",):
            top_k = config.get("top_k", 5)
            retrieved = node_input.get("retrieved", [])
            output_data = {
                "retrieved": [{"id": f"reranked_{i}", "content": f"Reranked document {i}", "score": round(0.98 - i * 0.03, 3)} for i in range(min(top_k, len(retrieved) or 5))],
                "reranked_count": min(top_k, len(retrieved) or 5),
            }
            message = f"Reranked to top {top_k} documents"

        elif category == "generator" or component_type in ("llm_generator",):
            model = config.get("model", "gpt-4o-mini")
            output_data = {
                "answer": f"Generated answer based on {len(node_input.get('retrieved', []))} retrieved documents using {model}.",
                "model": model,
                "tokens_used": 450,
            }
            message = f"Generated response using {model}"

        elif category == "storage" or component_type in ("kv_store", "graph_store", "vector_store"):
            output_data = {
                "stored": True,
                "storage_type": component_type,
            }
            message = f"Data stored via {component_type}"

        elif category == "agent" or component_type in ("query_router", "reflection_agent", "memory_agent"):
            if "router" in component_type:
                output_data = {
                    "routing": {"strategy": "dense_retrieval", "reasoning": "Factual query - simple vector search"},
                    "selected_strategy": "dense_retrieval",
                }
                message = "Routed to dense_retrieval strategy"
            elif "reflection" in component_type:
                output_data = {
                    "reflection": {"score": 8.5, "feedback": "Good answer with source citations"},
                    "needs_retry": False,
                }
                message = "Quality score: 8.5/10 - No retry needed"
            else:
                output_data = {
                    "context_updated": True,
                    "history_length": 2,
                }
                message = "Conversation memory updated"

        elif category == "planner" or component_type in ("corag_planner", "kag_planner"):
            strategy = config.get("strategy", "greedy")
            output_data = {
                "plan": {"strategy": strategy, "steps": ["retrieve", "rerank", "generate"]},
            }
            message = f"Created {strategy} retrieval plan with 3 steps"

        else:
            output_data = {"raw": f"Processed by {component_type}"}
            message = f"Executed {component_type}"

    except Exception as e:
        status = "failed"
        message = str(e)
        output_data = {"error": str(e)}

    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    return {
        "node_id": node["id"],
        "node_type": component_type,
        "label": label,
        "category": category,
        "status": status,
        "message": message,
        "output_data": output_data,
        "duration_ms": elapsed_ms,
    }


async def execute_pipeline(
    db: AsyncSession,
    pipeline_run: PipelineRun,
    definition: dict,
    *,
    redis=None,
) -> PipelineRun:
    """Execute a pipeline definition with DAG-based execution order.

    The definition is expected to have ``nodes`` (list) and ``edges`` (list).
    Each node is executed in topological order, with outputs from predecessor
    nodes passed as inputs to successor nodes.

    If *redis* is provided, real-time SSE events are published for each node.
    """
    run_id = pipeline_run.id
    pipeline_run.status = RunStatus.running
    pipeline_run.started_at = datetime.utcnow()
    await db.commit()

    nodes: list[dict] = definition.get("nodes", [])
    edges: list[dict] = definition.get("edges", [])

    _emit(redis, run_id, "run_started", {"total_nodes": len(nodes)})

    try:
        order = _topological_sort(nodes, edges)
        node_map = {n["id"]: n for n in nodes}

        results: list[dict[str, Any]] = []
        node_outputs: dict[str, dict] = {}
        input_data: dict[str, Any] = pipeline_run.input_params or {}

        for node_id in order:
            node = node_map[node_id]
            node_data = _get_node_data(node)
            is_composite = node.get("is_composite", False) or node.get("data", {}).get("is_composite", False)

            _emit(redis, run_id, "node_started", {
                "node_id": node_id,
                "component_type": node_data["componentType"],
                "is_composite": is_composite,
            })

            result = await _execute_node(node, input_data, node_outputs, edges)
            results.append(result)
            node_outputs[node_id] = result

            if result["status"] == "failed":
                _emit(redis, run_id, "node_failed", {
                    "node_id": node_id,
                    "error": result.get("message", "unknown error"),
                })
                raise RuntimeError(f"Node '{node_id}' failed: {result.get('message', 'unknown error')}")

            _emit(redis, run_id, "node_completed", {
                "node_id": node_id,
                "duration_ms": result.get("duration_ms", 0),
                "output_preview": _truncate_output(result.get("output_data", {})),
            })

        pipeline_run.status = RunStatus.completed
        pipeline_run.result = {
            "node_results": results,
            "total_nodes": len(results),
            "completed_nodes": sum(1 for r in results if r["status"] == "completed"),
            "total_duration_ms": sum(r.get("duration_ms", 0) for r in results),
        }
        _emit(redis, run_id, "run_completed", {})
    except CycleDetectedError as exc:
        pipeline_run.status = RunStatus.failed
        pipeline_run.error = str(exc)
        _emit(redis, run_id, "run_failed", {"error": str(exc)})
    except Exception as exc:
        pipeline_run.status = RunStatus.failed
        pipeline_run.error = str(exc)
        _emit(redis, run_id, "run_failed", {"error": str(exc)})
        logger.exception("Pipeline execution failed")

    pipeline_run.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(pipeline_run)
    return pipeline_run


def _truncate_output(output: dict, max_chars: int = 200) -> dict:
    """Create a truncated preview of output data for SSE events."""
    preview = {}
    for k, v in output.items():
        if isinstance(v, str) and len(v) > max_chars:
            preview[k] = v[:max_chars] + "..."
        elif isinstance(v, list):
            preview[k] = f"[{len(v)} items]"
        elif isinstance(v, dict):
            preview[k] = f"{{{len(v)} keys}}"
        else:
            preview[k] = v
    return preview
