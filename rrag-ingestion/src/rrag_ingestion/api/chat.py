"""Chat API – uses query pipelines as tools for LLM function-calling with full tracing and streaming."""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rrag_ingestion.dependencies import AuthContext, get_current_user
from rrag_ingestion.models.query_pipeline import (
    QueryPipeline,
    query_pipeline_to_tool,
    tool_name_to_pipeline_id,
)
from rrag_ingestion.services import llm_service
from rrag_ingestion.services.query_executor import execute_query_pipeline
from rrag_ingestion.services.query_pipeline_store import get_query_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()

# Redis-backed conversation store with TTL
_CONV_PREFIX = "rrag:conv:"
_CONV_TTL = 3600 * 24  # 24 hours


def _conv_key(workspace_id: str, conv_id: str) -> str:
    return f"{_CONV_PREFIX}{workspace_id}:{conv_id}"


def _get_conversation(request: Request, workspace_id: str, conv_id: str) -> list[dict]:
    raw = request.app.state.redis.get(_conv_key(workspace_id, conv_id))
    if raw is None:
        return []
    return json.loads(raw)


def _save_conversation(request: Request, workspace_id: str, conv_id: str, history: list[dict]) -> None:
    request.app.state.redis.set(
        _conv_key(workspace_id, conv_id), json.dumps(history), ex=_CONV_TTL
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    query_pipeline_ids: list[str] = Field(
        ..., min_length=1, description="Query pipelines available as tools"
    )
    model: str | None = Field(None, description="Explicit chat LLM model; overrides pipeline + tier")
    tier: str | None = Field(
        None, description="Model tier for ADR-0018 routing when no explicit model: fast | capable"
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1, le=16384)
    conversation_id: str | None = None


class ChatSource(BaseModel):
    id: str
    content: str
    score: float = 0.0
    metadata: dict = {}


class ChatTraceStep(BaseModel):
    step: str
    status: str
    duration_ms: float
    input_summary: dict = {}
    output_summary: dict = {}
    error: str | None = None


class ChatTrace(BaseModel):
    id: str
    pipeline_id: str
    pipeline_name: str
    query: str
    datastore_id: str = ""
    datastore_name: str = ""
    steps: list[ChatTraceStep]
    total_duration_ms: float


class ChatResponse(BaseModel):
    id: str
    conversation_id: str
    message: str
    answer: str
    sources: list[ChatSource] = []
    traces: list[ChatTrace] = []
    model: str
    tokens_used: int = 0
    duration_ms: float = 0.0


# -- Helpers ------------------------------------------------------------------


async def _get_datastore(request: Request, workspace_id: str, datastore_id: str) -> dict | None:
    from rrag_ingestion.db import stores as db
    async with request.app.state.db_session_factory() as session:
        return await db.get_datastore(session, workspace_id, datastore_id, redis=request.app.state.redis)


async def _load_pipelines(
    request: Request, workspace_id: str, pipeline_ids: list[str]
) -> dict[str, tuple[QueryPipeline, dict]]:
    """Load pipelines and their tool schemas. Returns {tool_name: (pipeline, tool_schema)}."""
    result: dict[str, tuple[QueryPipeline, dict]] = {}
    for pid in pipeline_ids:
        pipeline = await get_query_pipeline(workspace_id, pid)
        if pipeline:
            tool = query_pipeline_to_tool(pipeline)
            result[tool["function"]["name"]] = (pipeline, tool)
    return result


def _resolve_chat_params(
    req: ChatRequest,
    pipeline_map: dict[str, tuple[QueryPipeline, dict]],
) -> tuple[str, str, float, int]:
    """Resolve system prompt, model, temperature, max_tokens from pipeline generator configs.

    Pipeline generator config is used as the base; ChatRequest fields override if explicitly set.
    Model precedence (ADR-0018): explicit request model > pipeline generator model >
    tier-selected model > configured default.
    """
    from rrag_ingestion.services import llm_service

    # Use the first pipeline's generator config as base
    first_pipeline = next(iter(pipeline_map.values()))[0]
    gen = first_pipeline.generator

    system_prompt = gen.system_prompt
    model = req.model or gen.model or llm_service.select_model(req.tier)
    temperature = req.temperature if req.temperature != 0.7 else gen.temperature
    max_tokens = req.max_tokens if req.max_tokens != 2048 else gen.max_tokens

    return system_prompt, model, temperature, max_tokens


async def _execute_tool_call(
    request: Request,
    workspace_id: str,
    tool_name: str,
    tool_args: dict,
    pipeline_map: dict[str, tuple[QueryPipeline, dict]],
) -> tuple[str, list[ChatSource], ChatTrace | None]:
    """Execute a tool call by running the query pipeline. Returns (text_result, sources, trace)."""
    entry = pipeline_map.get(tool_name)
    if not entry:
        return f"Error: Unknown tool '{tool_name}'", [], None

    pipeline, _ = entry
    query = tool_args.get("query", "")
    if not query:
        return "Error: No query provided", [], None

    datastore = await _get_datastore(request, workspace_id, pipeline.datastore_id)
    if not datastore:
        return f"Error: DataStore '{pipeline.datastore_id}' not found", [], None

    result = await execute_query_pipeline(pipeline, query, datastore)

    # Build context text from sources using generator's context_template
    template = pipeline.generator.context_template
    parts = []
    for i, src in enumerate(result.sources):
        parts.append(
            template.format(index=i + 1, score=f"{src.score:.3f}", content=src.content)
        )
    context_text = "\n\n".join(parts) if parts else "No relevant documents found."

    sources = [
        ChatSource(id=s.id, content=s.content, score=s.score, metadata=s.metadata)
        for s in result.sources
    ]

    trace = ChatTrace(
        id=result.trace.id,
        pipeline_id=result.trace.pipeline_id,
        pipeline_name=result.trace.pipeline_name,
        query=result.trace.query,
        datastore_id=result.trace.datastore_id,
        datastore_name=result.trace.datastore_name,
        steps=[
            ChatTraceStep(**s.to_dict()) for s in result.trace.steps
        ],
        total_duration_ms=result.trace.total_duration_ms,
    )

    return context_text, sources, trace


# -- Non-streaming endpoint ---------------------------------------------------


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Chat with LLM using query pipelines as tools."""
    auth.require_workspace_role(workspace_id, "viewer")
    start = time.monotonic()
    chat_id = str(uuid.uuid4())
    conv_id = req.conversation_id or str(uuid.uuid4())
    history = _get_conversation(request, workspace_id, conv_id)

    # Load pipelines and build tools
    pipeline_map = await _load_pipelines(request, workspace_id, req.query_pipeline_ids)
    if not pipeline_map:
        raise HTTPException(status_code=400, detail="No valid query pipelines found")

    tools = [tool for _, tool in pipeline_map.values()]

    # Resolve chat params from pipeline generator config + request overrides
    system_prompt, model, temperature, max_tokens = _resolve_chat_params(req, pipeline_map)

    # Build messages
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    for msg in history[-20:]:
        messages.append(msg)
    messages.append({"role": "user", "content": req.message})

    all_sources: list[ChatSource] = []
    all_traces: list[ChatTrace] = []
    total_tokens = 0

    # First LLM call -- may produce tool calls
    try:
        response = await llm_service.completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice="auto",
        )
    except Exception as e:
        logger.error(f"LLM completion failed: {e}")
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")
    total_tokens += getattr(response.usage, "total_tokens", 0) if response.usage else 0

    assistant_msg = response.choices[0].message

    # Process tool calls (iterative -- support multiple rounds)
    max_rounds = 5
    rounds = 0
    while assistant_msg.tool_calls and rounds < max_rounds:
        rounds += 1
        messages.append(assistant_msg.model_dump())

        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            context_text, sources, trace = await _execute_tool_call(
                request, workspace_id, fn_name, fn_args, pipeline_map
            )
            all_sources.extend(sources)
            if trace:
                all_traces.append(trace)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": context_text,
            })

        # Follow-up LLM call with tool results
        try:
            response = await llm_service.completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice="auto",
            )
        except Exception as e:
            logger.error(f"LLM completion failed during tool loop: {e}")
            raise HTTPException(status_code=502, detail=f"LLM service error: {e}")
        total_tokens += getattr(response.usage, "total_tokens", 0) if response.usage else 0
        assistant_msg = response.choices[0].message

    answer = assistant_msg.content or ""

    # Save to conversation
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": answer})
    _save_conversation(request, workspace_id, conv_id, history)

    duration_ms = round((time.monotonic() - start) * 1000, 2)

    return ChatResponse(
        id=chat_id,
        conversation_id=conv_id,
        message=req.message,
        answer=answer,
        sources=all_sources,
        traces=all_traces,
        model=model,
        tokens_used=total_tokens,
        duration_ms=duration_ms,
    )


# -- Streaming endpoint -------------------------------------------------------


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    """Stream a chat response via SSE with tool-calling and tracing."""
    auth.require_workspace_role(workspace_id, "viewer")
    chat_id = str(uuid.uuid4())
    conv_id = req.conversation_id or str(uuid.uuid4())
    history = _get_conversation(request, workspace_id, conv_id)

    pipeline_map = await _load_pipelines(request, workspace_id, req.query_pipeline_ids)
    if not pipeline_map:
        raise HTTPException(status_code=400, detail="No valid query pipelines found")

    tools = [tool for _, tool in pipeline_map.values()]

    # Resolve chat params from pipeline generator config + request overrides
    system_prompt, model, temperature, max_tokens = _resolve_chat_params(req, pipeline_map)

    async def generate() -> AsyncGenerator[str, None]:
        nonlocal history
        yield _sse({"type": "start", "id": chat_id, "conversation_id": conv_id})

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        for msg in history[-20:]:
            messages.append(msg)
        messages.append({"role": "user", "content": req.message})

        all_sources: list[dict] = []
        all_traces: list[dict] = []

        # First call -- non-streaming to check for tool calls
        try:
            response = await llm_service.completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice="auto",
            )
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        assistant_msg = response.choices[0].message

        # Process tool calls
        max_rounds = 5
        rounds = 0
        while assistant_msg.tool_calls and rounds < max_rounds:
            rounds += 1
            messages.append(assistant_msg.model_dump())

            for tc in assistant_msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                yield _sse({
                    "type": "tool_call",
                    "tool_name": fn_name,
                    "tool_args": fn_args,
                })

                context_text, sources, trace = await _execute_tool_call(
                    request, workspace_id, fn_name, fn_args, pipeline_map
                )

                if sources:
                    source_dicts = [s.model_dump() for s in sources]
                    all_sources.extend(source_dicts)
                    yield _sse({"type": "sources", "sources": source_dicts})

                if trace:
                    trace_dict = trace.model_dump()
                    all_traces.append(trace_dict)
                    yield _sse({"type": "trace", "trace": trace_dict})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": context_text,
                })

            # Check for more tool calls
            try:
                response = await llm_service.completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice="auto",
                )
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})
                return
            assistant_msg = response.choices[0].message

        # Deliver the final answer
        if not assistant_msg.tool_calls:
            try:
                # If we already have the answer from the last non-streaming call,
                # emit it directly instead of making a redundant streaming call.
                full_answer = assistant_msg.content or ""
                if full_answer:
                    yield _sse({"type": "token", "content": full_answer})
                else:
                    # Fallback: stream generation if content was empty
                    async for chunk in llm_service.stream_completion(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ):
                        delta = ""
                        if chunk.choices and chunk.choices[0].delta.content:
                            delta = chunk.choices[0].delta.content
                        if delta:
                            full_answer += delta
                            yield _sse({"type": "token", "content": delta})

                # Save conversation
                history.append({"role": "user", "content": req.message})
                history.append({"role": "assistant", "content": full_answer})
                _save_conversation(request, workspace_id, conv_id, history)

                yield _sse({
                    "type": "done",
                    "answer": full_answer,
                    "sources": all_sources,
                    "traces": all_traces,
                })
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")


# -- Conversation management --------------------------------------------------


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "viewer")
    history = _get_conversation(request, workspace_id, conversation_id)
    return {"conversation_id": conversation_id, "messages": history}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    workspace_id: str = Query(..., description="Workspace ID"),
    auth: AuthContext = Depends(get_current_user),
):
    auth.require_workspace_role(workspace_id, "developer")
    request.app.state.redis.delete(_conv_key(workspace_id, conversation_id))
    return {"status": "deleted"}


# -- SSE helper ----------------------------------------------------------------


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
