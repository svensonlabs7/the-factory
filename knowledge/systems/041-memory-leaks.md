# 41. Memory Leaks

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

## What it is
In a garbage-collected language such as Python, a memory leak is memory that is still reachable but will never be used again: a global cache, list, registry or listener set that keeps growing. CPython frees unreachable objects through reference counting and its cycle collector, but anything still referenced from a live object is kept forever, by design.

Real leaks show up as memory that grows with work done and never levels off, until the process slows (swap, GC pressure) or is killed. To find one:
- watch the process's memory across repeated, identical work, which should plateau;
- diff `tracemalloc` snapshots to see which lines' allocations grew.

The fix is a bound on every long-lived container: a maximum size (LRU), a time-to-live, or removal when the owning work ends.

## When it is worth it
It matters for every long-running process: servers, daemons, workers. Short scripts and CLI commands end before leaks matter. The cheap discipline is that every module-level or long-lived container needs a stated bound or eviction, and a quick plateau check under repeated load. Heap profilers in production and per-request allocation budgets are for large, memory-sensitive services.

## How it fails
- **Unbounded cache:** keyed by request, user, URL or run ID with no eviction → grows with traffic forever.
- **Append-only registries:** listeners, callbacks or subscriptions added per request and never removed.
- **Keeping per-request data in module globals:** history lists, "last N" kept without trimming.
- **Reference cycles holding big objects,** together with `__del__` or C extensions, so they are freed late or not at all.
- **Misreading RSS:** compressed or swapped pages make memory look like it "grows" on first touch and "shrinks" at idle, so a leak is judged on the plateau under repeated identical load, not on one number.

## Review checklist
- [ ] **Does every long-lived container have a bound?** · Applies when: the diff adds a module-level, class-level or global dict, list, set or cache in a long-running process. · Block if: it can grow with traffic, runs or time and has no max size, TTL or removal.
- [ ] **Is per-request or per-run data released when the work ends?** · Applies when: the diff stores data keyed by a request, run or connection. · Block if: nothing removes the entry when that request, run or connection finishes.
- [ ] **Are registrations paired with removals?** · Applies when: the diff adds listeners, callbacks, subscriptions or background tasks at runtime. · Block if: there is no matching unregister or cancel.
- [ ] **Has a long-running path been checked for a plateau?** · Applies when: the diff makes a server or worker keep data across requests or runs (caches, buffers, history, registries). · Block if: there is no evidence (a `tracemalloc` diff, or RSS across repeated identical load) that memory levels off.

## In the factory
- `factory/intake/webhook_adapter.py:550,573-575`: `_recent_rejections` is pruned to `REJECTION_WINDOW` on every append. The replay directory is pruned by age (`_replayed`), and the per-request `ThreadPoolExecutor` in `/command/data` is closed by its `with` block. Right.
- `factory/intake/webhook_adapter.py:647,671`: `_pr_cache` only inserts. Merged and closed PRs are kept "for good" and are never evicted, even after `_recover` prunes their runs. That is about 2 KB per PR, roughly 2 MiB a year at 3 PRs a day and 21 MiB at the 30-a-day cap. Acceptable: the adapter is restarted on every deploy, and the amount is tiny. Bound it (an LRU of a few hundred) only if the process ever runs for months untouched.
- The live adapter (PID 40944, CPython 3.11) plateaus under repeated dashboard load (proof below): not leaking per request.
- Not applicable at today's load: production heap profiling.

## Proof
Live adapter RSS (`ps -o rss`) around batches of 300 `GET /command/data`:
```
A  before: 11.3 MB -> after 300: 24.6 MB -> 20 s later: 24.3 MB
A2 before round 2: 11.4 MB (idle pages compressed again) -> after 300 more: 24.7 MB -> after 300 more: 24.7 MB
```
The jump is the working set being paged back in. Repeated identical load does not grow it. `pytest -s scratchpad/mastery/041_memory.py` (B uses the adapter's real `_pr` and `_pr_cache` through `tests/test_adapter.py`'s fixture, with `gh` stubbed):
```
B  _pr_cache after 5,000 PRs: 5000 entries, +9823 KiB (2012 B per PR); entries ever removed: 0
B  at 3 PRs/day, without a restart: ~2.1 MiB/year
B  at 30 PRs/day, without a restart: ~21.0 MiB/year
C  lru_cache(maxsize=256) after 5,000 PRs: 256 entries, +748 KiB (capped)
```

## Related
042-garbage-collection.md, 002-caching.md, 044-backpressure.md, 043-thread-safety.md

## Sources
- "tracemalloc: Trace memory allocations", Python documentation: https://docs.python.org/3/library/tracemalloc.html
- "gc: Garbage Collector interface", Python documentation: https://docs.python.org/3/library/gc.html
