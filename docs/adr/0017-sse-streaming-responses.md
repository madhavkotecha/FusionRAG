# ADR-0017: Server-Sent Events for Streaming Responses

## Status

Accepted

## Context

RAG queries can take 2–5 seconds for complex multi-engine retrieval. Users need progressive feedback during this time:
- Which engines are being queried
- Retrieved sources before generation starts
- Token-by-token LLM output as it's generated
- Citation attachment as provenance is resolved

This is primarily one-directional: server → client.

## Decision

Use **Server-Sent Events (SSE)** for all real-time streaming in the system:

### Query Streaming (`POST /api/v1/ingestion/query/stream`)

| Event | Payload | When |
|-------|---------|------|
| `start` | `{ query_id }` | Query received and processing begins |
| `sources` | `[{ id, content, score }]` | Retrieval complete, sources available |
| `token` | `{ text }` | Each token from LLM generation |
| `done` | `{ id, answer, tokens_used, duration_ms }` | Complete response |
| `error` | `{ message }` | Processing failure |

### Job Monitoring (`GET /api/v1/ingestion/jobs/stream`)

| Event | Payload | When |
|-------|---------|------|
| `jobs` | `[{ id, status, progress, ... }]` | Job list snapshot (on change) |
| `idle` | `{}` | No active jobs |

### Frontend Integration
- Browser's native `EventSource` API (auto-reconnection built-in)
- Axios with `responseType: 'stream'` for POST-based SSE
- React state updated per event for progressive UI rendering

## Consequences

**Positive:**
- Native browser support (EventSource API)
- Automatic reconnection on connection drop
- One-directional simplicity — no handshake overhead
- Works through Traefik reverse proxy without special configuration
- Compatible with HTTP/2 multiplexing
- Progressive disclosure improves perceived performance

**Negative:**
- POST-based SSE requires custom implementation (EventSource only supports GET)
- No bidirectional communication (client can't send mid-stream messages)
- Connection limits per domain (~6 in HTTP/1.1, unlimited in HTTP/2)
- Long-lived connections may cause issues with some load balancers

## Alternatives Considered

1. **WebSockets**: Bidirectional — but overkill for one-way streaming, more complex proxy config
2. **Long polling**: Universally supported — but higher latency, more server load
3. **gRPC streaming**: Efficient binary protocol — but no native browser support, requires grpc-web proxy
4. **Polling**: Simplest — but poor UX for token-by-token streaming, high server load
