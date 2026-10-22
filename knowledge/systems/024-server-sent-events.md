# 24. Server-Sent Events

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

## What it is
Server-Sent Events (SSE) stream events from server to client over one long-lived HTTP response with `Content-Type: text/event-stream`. Browsers consume it with `EventSource`. The format is plain text:
- `data:` lines carry the payload;
- `event:` names the event type;
- `id:` sets the last event ID;
- `retry:` sets the reconnection delay in milliseconds;
- lines starting with `:` are comments, used as keep-alives;
- a blank line ends each event.

Reconnection is built in. When the stream drops, the client waits the retry delay, reconnects, and sends the last ID it saw in a `Last-Event-ID` header, so the server can resume from there. A `204` tells the client to stop. The HTML spec warns that "legacy proxy servers are known to... drop HTTP connections after a short timeout", and suggests a comment line about every 15 s.

SSE is one-way, server to client, which is simpler than WebSockets. Over HTTP/1.1 it counts against the browser's 6-connection limit per domain. HTTP/2 removes that limit.

## When it is worth it
SSE is worth it when clients need server-pushed updates promptly (live logs, progress, notifications, dashboards with many changes) and only the server talks. It is lighter than WebSockets: plain HTTP, built-in resume, proxy-friendly. It needs an async server, because each client holds a connection, and keep-alive comments to get through idle timeouts. When updates are infrequent and a delay of a poll interval is acceptable, short polling stays simpler.

## How it fails
- **No `id:` field:** a dropped connection (deploy, proxy idle timeout, network blip) loses every event sent while the client was away. `EventSource` reconnects, but the server cannot know what was missed.
- **Server ignores `Last-Event-ID`:** IDs are sent, but a reconnect starts from "now" anyway.
- **No keep-alives:** an idle stream is cut by a proxy, CDN or load balancer → constant reconnects, or 504 and 524 errors.
- **Buffering intermediary or compression:** events arrive in bursts or only at the end of the response.
- **Sync handler per stream:** each open stream occupies a worker thread (023-long-polling.md).
- **Connection limit over HTTP/1.1:** six tabs each open a stream, and the seventh request to the domain hangs.
- **Error status on reconnect:** a non-200 response or wrong content type fails the `EventSource` permanently, with no retry.

## Review checklist
- [ ] **Can a reconnecting client resume without gaps?** · Applies when: the diff adds or changes an SSE endpoint whose events matter (state changes, progress, log lines). · Block if: events carry no `id:`, or the server does not resume from `Last-Event-ID` (within a stated replay window).
- [ ] **Does the stream survive idle intermediaries?** · Applies when: the diff serves SSE through a proxy, tunnel or CDN. · Block if: no comment or heartbeat is sent more often than the shortest idle timeout on the path (the spec suggests every 15 s; Cloudflare's limit is 125 s).
- [ ] **Is the stream served without a thread per client?** · Applies when: the diff adds an SSE endpoint. · Block if: the generator blocks in a sync handler or thread instead of an async generator awaiting events.
- [ ] **Are buffering and caching off?** · Applies when: the diff adds an SSE route. · Block if: the response can be cached, compressed or buffered by the app or an intermediary (`Cache-Control: no-cache` missing, or compression applied to `text/event-stream`).
- [ ] **Is SSE needed over polling?** · Applies when: the diff replaces polling with SSE. · Block if: updates are infrequent and the existing poll delay is acceptable for what the client shows.

## In the factory
- The factory has no SSE. The dashboard short-polls `/command/data` every 15 s (`factory/intake/command.html:128`). That is right for one operator watching runs that take minutes (023-long-polling.md).
- The one place SSE would earn its keep is streaming a live run log to the dashboard. If it is added, all of these apply:
  - it must be `async`;
  - it must send `id:` lines and resume from `Last-Event-ID`;
  - it must send a comment at least every 15 s, well under Cloudflare's 125 s limit through the tunnel;
  - the stream must stay off the sync `/command/data` handler.
- Not applicable at today's load: SSE endpoints, replay buffers and HTTP/2-specific tuning.

## Proof
`python client.py` in `knowledge/systems/proofs/024/` runs `sse_app.py` under real uvicorn (Python 3.11, FastAPI `StreamingResponse`). Events 1 to 12 are produced every 0.3 s. The server cuts each stream after 1 s, as a proxy or deploy would. The client is a minimal `EventSource` over httpx that honours `retry:` and sends `Last-Event-ID`:
```
A  no id field        : 3 reconnects, received [1, 2, 3, 5, 6, 7, 8, 10, 11, 12], missed [4, 9]
B  id + Last-Event-ID : 3 reconnects, received [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], missed []
```
Every drop loses whatever was sent during the reconnect delay, unless events carry IDs and the server resumes from the last one.

## Related
023-long-polling.md, 022-websockets.md, 016-pub-sub.md, 015-message-queues.md, 011-timeouts.md

## Sources
- "Server-sent events", HTML Living Standard (WHATWG): https://html.spec.whatwg.org/multipage/server-sent-events.html
- "Using server-sent events", MDN Web Docs: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
