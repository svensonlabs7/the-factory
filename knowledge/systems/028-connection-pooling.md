# 28. Connection Pooling

Track: G. Data · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)httpx\.client|requests\.session|connectionpool|pool_size|max_connections|keep.?alive|create_connection`

## What it is
Opening a connection is expensive: a TCP handshake, a TLS handshake, then authentication and, for a database, a server process or session. A connection pool opens a small set of connections once and lends them to requests, which return them when done. Requests skip the setup cost, and the server sees a bounded number of connections instead of one per request.

The pool's settings are its contract:
- **Size:** SQLAlchemy's `QueuePool` defaults to 5, plus `max_overflow` 10.
- **Wait timeout:** 30 s by default, after which a checkout gives up.
- **Health checks:** `pool_pre_ping` tests a connection before use; `pool_recycle` retires old ones.

Bigger is not faster. HikariCP's write-up shows an Oracle system whose response time fell "from ~100ms to ~2ms" when its pool shrank "from 2048 down to just 96". It suggests `(cores × 2) + effective spindles` as a starting size, because once connections outnumber cores the database only time-slices. Excess requests should wait in the application's queue, not in the database.

## When it is worth it
Pooling is worth it whenever a process makes repeated calls to the same server over a network: a database, an internal service, an HTTP API with TLS. Most clients pool by default: database engines, `requests.Session`, `httpx.Client`. The work is in sizing the pool to the server's capacity, bounding the wait, and returning connections reliably. A pool is unnecessary for rare calls, or for local IPC. For calls made through a CLI process, the process start dominates and no pool can help without replacing the CLI.

## How it fails
- **Connection leak:** a code path checks a connection out and never returns it (an exception before `close()`, a missing `with`) → the pool drains, and every later request waits out the timeout and fails.
- **Pool too big:** every app instance opens dozens of connections → the database hits `max_connections`, or thrashes context switching, and gets slower.
- **Pool too small with long holds:** connections are held across slow work (remote calls, user think time) → requests queue for a connection even though the database is idle.
- **Stale connections:** a firewall, load balancer or server idle timeout silently drops pooled connections → the first query on each fails, unless there is a pre-ping or recycle.
- **No wait timeout:** pool exhaustion blocks request threads forever, instead of failing fast.
- **Shared across fork:** a pool created before `fork()` lets parent and child use the same socket → corrupted protocol state.
- **New client per request:** `httpx.Client()` or a fresh engine created per call → every request pays the full handshake, which is the cost pooling exists to avoid.

## Review checklist
- [ ] **Is every checkout returned on every path?** · Applies when: the diff acquires pooled connections, sessions or clients. · Block if: a connection is obtained without `with`, `try/finally` or a framework-managed scope that returns it even on exceptions.
- [ ] **Is the pool sized and bounded against the server?** · Applies when: the diff configures a pool, or adds instances or workers that each have one. · Block if: pool size × instances can exceed the server's connection limit, or the checkout has no timeout.
- [ ] **Are connections reused, not rebuilt per request?** · Applies when: the diff calls a network service on a hot request path or in a loop over items. · Block if: it creates a new HTTP client, database engine or session per call instead of reusing a long-lived one. Spawning a CLI per call at a few calls a minute, as the adapter does with `gh` to keep its token out of the process, is a deliberate exception.
- [ ] **Are stale connections handled?** · Applies when: the diff configures a long-lived pool to a server behind firewalls, proxies or idle timeouts. · Block if: there is no pre-ping, recycle or retry-on-disconnect.
- [ ] **Is a connection held only for the query?** · Applies when: the diff holds a pooled connection or transaction across slow work. · Block if: the connection stays checked out across remote calls, sleeps or waits that do not need it.

## In the factory
- There is no database and no pool. The adapter reaches GitHub by spawning the `gh` CLI for every call (`_run`, `factory/intake/webhook_adapter.py:313-321`), so each call pays a new process and a new TLS connection:
  - about 300 ms per `gh api rate_limit`, against 23 ms per request on a pooled keep-alive connection to the same host (proof A, C);
  - a process start alone is 37 ms.

  That is right at this load: about two `gh` calls per 15 s poll while waiting for a gate, and a cached dashboard. The CLI also keeps the GitHub token in the macOS keychain (`gh auth status` reports `keyring`) and out of the adapter's memory and environment (067-secrets-management.md). A pooled HTTP client would be about 13 times faster per call, but would need the token in the process. That trade is not worth making until `gh` latency matters, for example the cold dashboard load at hundreds of PRs (027-n-plus-one-queries.md).
- The connections that do matter are pooled by their owners: uvicorn keeps HTTP/1.1 connections alive, and `cloudflared` holds long-lived connections to Cloudflare's edge.
- Not applicable at today's load: database pools, pool sizing and pre-ping.

## Proof
`python knowledge/systems/proofs/028_pooling.py` (Python 3.11, httpx, SQLAlchemy `QueuePool` on a SQLite file. A and C use the real GitHub API read-only, and `/rate_limit` does not count against the limit):
```
A  new connection per request: median   85.6 ms
A  pooled keep-alive client:   median   22.8 ms (first request 85.6 ms opens the connection)
B  20 concurrent, pool 5, hold 0.3 s: 20 served, 0 timed out; max wait for a connection 0.92 s
B  after 5 leaked connections: next request -> TimeoutError (QueuePool limit of size 5 overflow 0 reached)
C  gh --version (process start only):   37.1 ms; gh api rate_limit (start + new TLS + request):  304.4 ms
```
In B the pool of 5 served 20 requests by queueing them, with waits up to 0.92 s, inside the 1 s timeout. Five leaked connections were enough to fail the next request.

## Related
027-n-plus-one-queries.md, 011-timeouts.md, 044-backpressure.md, 067-secrets-management.md, 091-latency.md, 041-memory-leaks.md

## Sources
- "About Pool Sizing", HikariCP wiki (Brett Wooldridge): https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing
- "Connection Pooling", SQLAlchemy 2.0 documentation: https://docs.sqlalchemy.org/en/20/core/pooling.html
