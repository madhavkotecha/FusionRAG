# ADR-0005: Async Document Ingestion with RQ (Redis Queue)

## Status

Accepted

## Context

Document ingestion involves potentially long-running operations: file parsing, chunking, embedding generation (OpenAI API calls), and index building. These cannot run synchronously in an HTTP request.

## Decision

Use **RQ (Redis Queue)** for async job processing:
- Ingestion API enqueues jobs to a Redis queue
- A separate RQ worker container dequeues and processes jobs
- Job status is tracked in Redis and streamed to the frontend via **Server-Sent Events (SSE)**
- Both the API server and worker share the same Docker image (different entrypoints)

SSE provides real-time progress updates without WebSocket complexity.

## Consequences

**Positive:**
- Long-running jobs don't block API responses
- Worker can be scaled independently
- RQ is simple and lightweight (vs Celery)
- SSE is simpler than WebSockets for one-way streaming
- Redis already in the stack for caching

**Negative:**
- RQ is single-threaded per worker (Python GIL)
- No built-in retry with exponential backoff (requires custom implementation)
- SSE requires client-side reconnection logic
- Job state in Redis is ephemeral (lost on Redis restart without persistence)

## Alternatives Considered

1. **Celery**: More features but significantly more complex
2. **Background threads**: No scaling, process crashes lose jobs
3. **WebSockets**: Bidirectional overkill for status updates
4. **Polling**: Simpler but higher latency and server load
