# 50. Cache Invalidation

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

## What it is
Cache invalidation is making cached copies stop being served once the source changes. There are three ways:
- **Expiry:** a TTL, simple and bounded, but stale for up to the TTL.
- **Explicit invalidation on write:** delete or update the entry when the data changes.
- **Versioned keys:** the key carries a version, so a change makes the old key unreachable.

HTTP builds the second into the protocol (RFC 9111 §4.4): a cache "MUST invalidate the target URI when it receives a non-error status code in response to an unsafe request method". It can do so only for "the caches it travels through".

The subtle part is concurrency. Facebook's memcache paper ("Scaling Memcache at Facebook", NSDI 2013) describes their look-aside cache. On a write, the web server updates the database and then deletes the key: "we choose to delete cached data instead of updating it because deletes are idempotent". Deleting is still not enough. A stale set occurs "when a web server sets a value in memcache that does not reflect the latest value", because "concurrent updates to memcache get reordered": a reader that read the old value before the write fills the cache after the delete.

Their fix is leases. On a miss the cache hands out a lease token, a delete voids outstanding leases, and a fill with a void token is rejected. Rate-limiting lease issue also tamed thundering herds: the peak database query rate fell from 17K/s to 1.3K/s.

## When it is worth it
Explicit invalidation is worth it when data must be fresh soon after a write and the writer knows which keys changed. Think of a user's own edits, prices or permissions. TTL-only caching is enough when a bounded staleness is acceptable to every reader. Concurrency-safe fills (leases, versioned or compare-and-set writes) are needed when reads and writes to the same keys interleave at volume. With one writer and a short TTL on low-stakes data, a TTL alone is the proportionate choice, plus a direct invalidation where the writer is the same process.

## How it fails
- **Stale set race:** read old value, the write and invalidation happen, then the old value is filled into the cache → stale until the TTL, or forever with no TTL. It happens with update-then-set and with update-then-delete alike (proof A).
- **Invalidating before writing:** the cache is deleted, a reader refills the old value, then the database is updated → stale.
- **Invalidation lost:** the delete message is dropped or the invalidating process crashes → stale with no bound. TTLs are the safety net.
- **Keys missed:** a write changes data feeding several cached views (lists, counts, derived pages), but only one key is invalidated.
- **Writer does not invalidate its own change:** the process that made the change keeps serving its own cached pre-change value until the TTL (proof C).
- **Invalidation storms:** a hot key invalidated on every write sends every reader to the source (thundering herd).

## Review checklist
- [ ] **Can a concurrent fill write back a value older than the latest write?** · Applies when: the diff adds cache-aside reads and writes or invalidations to the same keys from concurrent code. · Block if: a fill can land after a newer write's invalidation, with no lease, version check or compare-and-set, and no TTL short enough for readers to tolerate the result.
- [ ] **Does every write invalidate every view it affects?** · Applies when: the diff changes data that feeds cached values. · Block if: some cached key or derived view that depends on the changed data is neither invalidated nor bounded by a TTL readers can accept.
- [ ] **Is the order write-then-invalidate?** · Applies when: the diff adds invalidation code. · Block if: the cache is invalidated before the source is updated, or updated in place where a delete would be idempotent.
- [ ] **Is there a TTL backstop?** · Applies when: the diff relies on explicit invalidation. · Block if: entries have no expiry, so one lost invalidation leaves them stale forever.
- [ ] **Does the writer invalidate its own reads?** · Applies when: the same process both changes a resource and serves a cached view of it. · Block if: the change does not invalidate the process's own cached entry, and readers act on the freshness of that view.

## In the factory
- The only application cache, `_pr_cache` (`factory/intake/webhook_adapter.py:646-672`), relies on expiry alone: 60 s for open PRs, and never for merged or closed ones.
  - The never-expiring CLOSED entry is already a row (035-eventual-consistency.md).
  - There is one writer, a dashboard reader, and no fills racing invalidations, so leases are unnecessary.
- The adapter does not invalidate its own change. When it pushes a fix round, the PR's checks change, but the cached entry still shows the previous head's checks until the TTL (proof C). The dashboard can show "tests fail" for up to 60 s after a push it already knows about. That is cosmetic; a one-line `_pr_cache.pop(pr_url, None)` after the push would make the writer's own view fresh. The gate itself never reads this cache (`_gate_results` calls `gh` directly).
- The dashboard's HTTP responses are not cached anywhere (002-caching.md), so RFC 9111 invalidation does not come into play.
- Not applicable at today's load: leases, versioned keys and invalidation messaging.

## Proof
`pytest -s knowledge/systems/proofs/050_invalidation.py` (Python 3.11). A and B use real threads, with the interleaving forced by events: the reader reads the old value, then the writer updates and invalidates, then the reader fills. C is the real `_pr` through `tests/test_adapter.py`'s fixture:
```
A  update db, then set cache:    db 12, cache 10 -> STALE until TTL
A  update db, then delete cache: db 12, cache 10 -> STALE until TTL
B  delete + leases:              db 12, cache None -> consistent
C  dashboard before the push: tests fail; right after the push (within the 60 s TTL): tests fail
```

## Related
002-caching.md, 035-eventual-consistency.md, 039-race-conditions.md, 036-optimistic-locking.md, 043-thread-safety.md

## Sources
- Rajesh Nishtala et al., "Scaling Memcache at Facebook", NSDI 2013 (sections 2 and 3.2.1): https://www.usenix.org/system/files/conference/nsdi13/nsdi13-final170_update.pdf
- RFC 9111, "HTTP Caching", section 4.4 (Invalidating Stored Responses): https://www.rfc-editor.org/rfc/rfc9111.html#section-4.4
