# 2. Caching

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)\bcache\b|_cache\b|lru_cache|cache_ttl|\bttl\b`

## What it is
A cache keeps copies of results so later requests skip the slow or expensive source: a backend call, a database query, a computation, a network fetch. Its value is the hit ratio times the cost it saves. Its price is staleness and complexity, because every cached value is an eventually consistent copy (035-eventual-consistency.md).

HTTP standardizes the vocabulary (RFC 9111):
- **Freshness:** a response is reusable while fresh, as set by `max-age` or `Expires`.
- **`no-cache`:** "MUST NOT be used to satisfy any other request without forwarding it for validation".
- **`no-store`:** do not keep it at all.
- **`private`:** keeps a response out of shared caches.
- **Heuristic freshness:** without explicit expiry, a cache may guess one, typically from `Last-Modified`.

Amazon's Builders' Library names the operational dangers:
- **Modal behaviour:** a system that behaves differently with a cold cache. "A cold, flushed, or failed cache" sends a surge to the backend, often right after a deploy.
- **Stampedes:** many clients miss the same key at once. Request coalescing ensures only one load per key is in flight.
- **Missing negative caching:** errors are not cached, so a failing resource is hammered.
- **Soft versus hard TTL:** keep serving the old value when a refresh fails, until a hard limit.

## When it is worth it
A cache is worth it when the same results are read repeatedly, the source is slow, costly or rate-limited, and readers tolerate a stated staleness. The Builders' Library warns it pays only if results are reused across requests. Size it from the access pattern (LRU over a skewed workload: proof A). Plan for the cold start, stampedes, and the failure of the source. Caching a fast local operation, or data that is rarely re-read, adds staleness and code for nothing.

## How it fails
- **Cold cache as an outage trigger:** a deploy or flush empties the cache, and the backend sees several times its normal load at once (proof A: about twice as many backend calls in the first 1,000 requests).
- **Stampede:** a popular key expires and 50 concurrent requests each call the backend (proof B).
- **No negative caching:** a failing or missing resource is re-fetched on every request, amplifying the failure.
- **Hard expiry on refresh failure:** the cached value is discarded when the refresh errors, so a brief source outage blanks data that was fine a minute ago (proof C).
- **Stale forever:** an entry treated as immutable changes (035-eventual-consistency.md).
- **Unbounded growth:** a cache with no size limit or eviction is a memory leak (041-memory-leaks.md).
- **Private data in a shared cache:** a per-user response without `Cache-Control: private` or `no-store` is stored by a CDN or proxy and served to others.

## Review checklist
- [ ] **Is staleness bounded and acceptable?** · Applies when: the diff adds a cache or changes a TTL. · Block if: there is no TTL or invalidation, or the stated staleness exceeds what readers of the data can tolerate.
- [ ] **Can concurrent misses stampede the source?** · Applies when: the diff adds a cache in front of a slow, costly or rate-limited source read concurrently. · Block if: concurrent misses for the same key each call the source, at a concurrency the source cannot absorb, with no coalescing or locking.
- [ ] **Does the system survive a cold cache?** · Applies when: the diff puts a cache in front of a source sized for the cached load. · Block if: an empty cache (deploy, restart, flush) would send more load than the source can take, with no warm-up, throttling or coalescing.
- [ ] **Are failures handled deliberately?** · Applies when: the diff caches results of a call that can fail. · Block if: errors are cached as successes, or failures are retried on every request with no negative caching or backoff, on a path called frequently.
- [ ] **Is the cache bounded?** · Applies when: the diff adds an in-process cache. · Block if: it has no maximum size or eviction and its keys grow with traffic or data.
- [ ] **Are per-user or private responses kept out of shared caches?** · Applies when: the diff serves authenticated or per-user content over HTTP through a proxy or CDN. · Block if: the response has no `Cache-Control: private` or `no-store`, and a cache rule could store it.

## In the factory
- The one application cache is `_pr_cache` (`factory/intake/webhook_adapter.py:646-672`): PR state for the dashboard, open PRs for 60 s, merged and closed ones kept.
  - It is never evicted, so it grows until the adapter restarts, about 2 KB per PR (041-memory-leaks.md; corrected in review 80), and CLOSED is wrongly treated as final (035-eventual-consistency.md's row).
  - Its cold start is the one-call-per-PR fan-out on 8 threads (027-n-plus-one-queries.md).
  - Concurrent misses can duplicate a `gh` call, which is harmless at one operator's load (043-thread-safety.md).
  - On a refresh failure it drops the stale entry and returns `None` (proof C), so a GitHub blip blanks an open PR's checks until the next good poll. That is cosmetic; serving the stale entry (a soft TTL) would be the one-line improvement.
  - It does no negative caching, so a failing PR is retried every poll, at most once per PR every 15 s.
- The dashboard responses (`/command`, `/command/data`) send no `Cache-Control` (live headers: only `date`, `server`, `content-length`, `content-type`). Neither has `Last-Modified`, so no heuristic freshness applies, and Cloudflare does not cache HTML or JSON by default. That is right today. An explicit `Cache-Control: no-store` on these authenticated, live pages would keep it right if a cache rule is ever added.
- The build caches (uv, the image pinned by digest) are content-addressed (107-build-caching.md).
- Not applicable at today's load: shared caches (Redis, Memcached), request coalescing and cache warm-up.

## Proof
`pytest -s knowledge/systems/proofs/002_caching.py` (Python 3.11). A is a seeded Zipf workload of 20,000 reads over 10,000 keys, with a 50 ms backend. B uses real threads and a 100 ms backend. C is the real `_pr` through `tests/test_adapter.py`'s fixture:
```
A  LRU size    10: hit ratio 22.8%, mean latency  38.6 ms; backend calls: first 1,000 requests 773, a later 1,000 771
A  LRU size   100: hit ratio 53.1%, mean latency  23.4 ms; backend calls: first 1,000 requests 482, a later 1,000 468
A  LRU size  1000: hit ratio 76.8%, mean latency  11.6 ms; backend calls: first 1,000 requests 391, a later 1,000 208
B  50 concurrent misses, plain cache-aside : backend called 50 times
B  50 concurrent misses, request coalescing: backend called 1 times
C  OPEN PR cached an hour ago, refresh fails: _pr returns None (the cached state is dropped, not served stale)
```

## Related
050-cache-invalidation.md, 035-eventual-consistency.md, 041-memory-leaks.md, 043-thread-safety.md, 027-n-plus-one-queries.md, 107-build-caching.md, 048-cdn.md

## Sources
- RFC 9111, "HTTP Caching": https://www.rfc-editor.org/rfc/rfc9111.html
- "Caching challenges and strategies", Amazon Builders' Library: https://builder.aws.com/content/3K9TeXp6strMiJ4vhakpRD7BQWO/caching-challenges-and-strategies
