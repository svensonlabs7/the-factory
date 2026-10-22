# 23. Long Polling

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

## What it is
Long polling is how a client waits for server-side changes over plain HTTP without asking over and over. The client sends a request. The server holds it open until there is something new or a timeout passes, then answers. The client immediately sends the next one. Compared with short polling (ask every N seconds), changes arrive within about one network transit instead of up to N seconds later, and idle periods cost one request per timeout instead of one per interval.

RFC 6202 lists the costs:
- every held request ties up a connection and server resources;
- each message still carries full HTTP headers;
- the worst-case latency is "over three network transits";
- intermediaries time out idle requests. A 30 s hold is the safer default, and 120 s has worked in experiments. Cloudflare's own origin timeout is 125 s, after which it returns 524.

## When it is worth it
Long polling is worth it when clients need changes quickly (seconds or less), changes are infrequent compared with any short-poll interval that would be fast enough, and SSE or WebSockets are not available or not worth their machinery. Short polling is the simpler, more robust choice when a few clients can tolerate a delay of a poll interval: it holds nothing open, needs no change-notification plumbing on the server, and survives every proxy. For many concurrent clients, long polling only scales on an async server, because each waiting client holds a connection.

## How it fails
- **Blocking long poll in a thread pool:** the hold is a `time.sleep` loop in a sync handler → each waiting client occupies a worker thread (anyio's default pool is 40), and every other sync endpoint queues behind them.
- **Hold longer than an intermediary's timeout:** the proxy, load balancer or CDN closes the request first → clients see 504 or 524 errors instead of an empty answer.
- **Lost update between polls:** the client re-polls without saying what it last saw → a change that happened between responses is missed. Pass a version or cursor.
- **Cached responses:** an intermediary caches the long-poll answer → clients see stale data. Send `Cache-Control: no-cache`.
- **Connection limits:** several tabs each hold a long poll → the browser's per-host connection limit starves other requests.
- **Thundering re-poll:** a change wakes thousands of held requests at once, and they all re-poll together.

## Review checklist
- [ ] **Does the hold avoid tying up a thread?** · Applies when: the diff adds an endpoint that waits for a change before answering. · Block if: the wait is a blocking sleep or poll loop in a sync (`def`) handler or worker thread, instead of an async wait on an event or condition.
- [ ] **Is the hold shorter than every intermediary's timeout?** · Applies when: the diff sets a long-poll hold or a streaming idle time on a route served through a proxy, tunnel or CDN. · Block if: the hold is at or above the shortest timeout on the path (125 s at Cloudflare). RFC 6202's 30 s is the safe default.
- [ ] **Can the client miss a change between polls?** · Applies when: the diff adds a long-poll or polling client. · Block if: the request carries no version, cursor or last-seen ID, so a change made between responses can be skipped.
- [ ] **Is caching disabled on the poll response?** · Applies when: the diff adds a long-poll route. · Block if: the response can be cached by an intermediary (no `Cache-Control: no-cache` or `no-store`).
- [ ] **Is long polling needed at all?** · Applies when: the diff replaces short polling with long polling, SSE or WebSockets. · Block if: the clients are few and the existing poll interval's delay is acceptable for what they show.

## In the factory
- The dashboard short-polls `/command/data` every 15 s (`factory/intake/command.html:128`). That is right:
  - there is one operator, a 15 s delay is fine for runs that take minutes, and nothing is held open through the tunnel;
  - the cost is about 5,700 requests a day, the bulk of the access log (059-logging.md).
- `/command/data` is a sync handler (`factory/intake/webhook_adapter.py:692`). Turning it into a long poll as written would put each waiting dashboard tab on a threadpool thread, as proof B shows. A long poll there would have to be `async def`, wait on an event, and hold well under Cloudflare's 125 s.
- The adapter waits on GitHub by short polling `gh pr checks` every 15 s (016-pub-sub.md). GitHub offers no long-poll endpoint for checks.
- Not applicable at today's load: long polling, SSE and WebSockets for the dashboard.

## Proof
`python harness.py` in `knowledge/systems/proofs/023/` runs `lp_app.py` under real uvicorn on Python 3.11, with httpx clients. A scales the dashboard's 15 s poll down to 1 s: 8 state changes at seeded random times over 16 s. B uses 45 held requests, past anyio's default of 40 threads:
```
A  short poll every 1 s :  15 requests in 17 s; change seen after mean    375 ms, max    979 ms
A  long poll, hold 4 s  :   9 requests in 17 s; change seen after mean      1 ms, max      1 ms
B  45 clients holding /longpoll_sync : a plain `def` request took   3536 ms
B  45 clients holding /longpoll      : a plain `def` request took      4 ms
```
Long polling sees changes about 375 times sooner, with fewer requests. Holding the wait in sync handlers starves every other sync endpoint until the holds expire.

## Related
024-server-sent-events.md, 022-websockets.md, 016-pub-sub.md, 043-thread-safety.md, 011-timeouts.md, 044-backpressure.md

## Sources
- RFC 6202, "Known Issues and Best Practices for the Use of Long Polling and Streaming in Bidirectional HTTP": https://www.rfc-editor.org/rfc/rfc6202.html
- "Error 524: a timeout occurred", Cloudflare documentation: https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/
