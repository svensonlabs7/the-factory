# 43. Thread Safety

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

## What it is
Code is thread-safe when it behaves correctly while several threads run it, or touch its data, at the same time. In CPython, the global interpreter lock (GIL) makes single operations on built-in types atomic: `list.append`, `d[k] = v`, `deque.append`. Compound operations are not: `i = i + 1`, `d[k] = d[k] + 1`, and check-then-act. A thread can be switched out between the read and the write.

Whether such a sequence actually interleaves depends on where the interpreter checks for a thread switch. That is an implementation detail. Python 3.10+ rarely switches inside a bare `n += 1`, but does at any function call, and free-threaded Python (3.13t) removes the GIL entirely. So "it never failed" is not evidence of safety.

The tools:
- don't share (confine each object to one thread);
- share only immutable data;
- use atomic operations;
- guard compound updates with a lock;
- in async code, keep to one event-loop thread, and never block it.

## When it is worth it
It matters wherever more than one thread exists. In web services that is almost everywhere: threadpool handlers, background workers, timers, executors. Prefer confinement, one owner per piece of state, over locks. Use a lock only around the compound updates that are actually shared. Concurrent collections and lock-free structures are for hot, contended paths.

## How it fails
- **Read-modify-write without a lock:** counters, totals or lists lose updates under load, silently.
- **"The GIL protects me":** code is correct only by interpreter accident → it breaks on a version change, on a call added in the middle, or on free-threaded Python.
- **Check-then-act on a cache:** many threads miss together and all do the expensive work (a stampede). That is usually only waste, but a disaster if the work has side effects.
- **Blocking the event loop:** a sync call or lock wait inside `async def` stalls every request on that loop (see 057-liveness-readiness-probes.md).
- **Mutable module globals touched from handlers that run in a threadpool (`def`)** with no thought for concurrency.

## Review checklist
- [ ] **Is every mutable shared object either confined to one thread or locked?** · Applies when: the diff adds module-level or class-level mutable state, or touches it from a `def` handler, a worker or an executor. · Block if: two threads can perform a compound update (read-modify-write, check-then-act) on it with no lock.
- [ ] **Does correctness rely on the GIL?** · Applies when: the diff updates shared counters, lists or dicts from several threads. · Block if: the argument for safety is "it is atomic in CPython" for anything beyond a single built-in operation.
- [ ] **Do `async def` handlers avoid blocking calls?** · Applies when: the diff adds or changes an `async def` handler. · Block if: it does slow blocking I/O (network, subprocess, sleep, a long lock wait) on the event loop instead of awaiting it or using a plain `def` (threadpool).
- [ ] **Is a cache stampede harmless?** · Applies when: the diff adds a check-then-fill cache shared by threads. · Block if: concurrent misses would repeat work with side effects, or work expensive enough to overload a dependency at the expected concurrency.

## In the factory
- `factory/intake/webhook_adapter.py:151,167,612`: threads are confined by design. One run worker (`max_workers=1`) owns run execution and each run's meta. The `alive_at` thread only writes HEARTBEAT under `HEARTBEAT_LOCK` (`:532`). `_recent_rejections` and `_burst_open` (`:550-551`) are touched only from `async` handlers on the event loop. Right.
- `factory/intake/webhook_adapter.py:647,658,691-700`: `_pr_cache` is the one structure shared across threads (the `def command_data` threadpool, plus its own pool of 8). Single dict operations are atomic, so it cannot be corrupted. On a cold cache, concurrent lookups of one PR each call `gh`, which is harmless at one operator's dashboard load.
- The live adapter runs CPython 3.11.15 with the GIL enabled.
- Not applicable at today's load: a lock or single-flight on `_pr_cache`, and concurrent collections.

## Proof
`pytest -s scratchpad/mastery/043_thread_safety.py` (Python 3.11; B uses the adapter's real `_pr` through `tests/test_adapter.py`'s fixture, with `gh` stubbed to take 0.2 s):
```
A  8 threads x 200,000 `n += 1`: n = 1,600,000 (expected 1,600,000; lost 0)
B  8 concurrent _pr() for one URL, cold cache: gh called 8 times in 0.2 s; cached after: True
B  a 9th call right after: gh called 0 times (cache hit)
```
With a call inside the read-modify-write (`n = add(n, 1)`), giving the interpreter a switch point, the same 3.11 interpreter loses most of the updates:
```
A2 8 threads x 200,000 `n = add(n, 1)`: n = 394,165 (expected 1,600,000; lost 1,205,835)
```
Bare `+=` survived only because 3.11 does not switch inside it. A free-threaded build (3.13t) was not tested; none is installed here.

## Related
039-race-conditions.md, 040-deadlocks.md, 057-liveness-readiness-probes.md, 002-caching.md

## Sources
- "What kinds of global value mutation are thread-safe?", Python Library FAQ: https://docs.python.org/3/faq/library.html#what-kinds-of-global-value-mutation-are-thread-safe
- "Concurrency and async / await", FastAPI documentation: https://fastapi.tiangolo.com/async/
