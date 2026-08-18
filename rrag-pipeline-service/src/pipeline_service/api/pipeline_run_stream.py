from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/pipelines/{pipeline_id}/runs/{run_id}/stream")
async def stream_pipeline_run(pipeline_id: str, run_id: str, request: Request):
    """SSE endpoint for real-time pipeline run progress."""
    redis = request.app.state.redis

    async def event_generator():
        pubsub = redis.pubsub()
        channel = f"pipeline_run:{run_id}"
        await pubsub.subscribe(channel)
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    event_type = data.pop("event", "message")
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                    if event_type in ("run_completed", "run_failed"):
                        break
                else:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
