# 42. Garbage Collection

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

## What it is
Garbage collection frees memory the program can no longer reach. CPython does it in two layers. Reference counting is primary: every object counts the references to it and is freed the moment the count hits zero, so most memory is released immediately and predictably. Reference counting cannot free a cycle (A refers to B, B refers to A), so a second layer, the cyclic collector, periodically walks container objects (lists, dicts, class instances) and frees groups that are reachable only from each other.

The cyclic collector is generational. New containers start young and are scanned often. Survivors are promoted and scanned rarely, because most objects die young. A full collection walks every tracked container and stops the interpreter while it runs, so its pause grows with the number of long-lived objects. `gc.freeze()` moves everything that exists into a permanent generation the collector skips, which is the usual tool for big, static heaps.

## When it is worth it
Every Python service already gets GC, so the question is when to tune it. Leave the defaults alone unless a measurement shows GC pauses in the latency tail or GC time in a profile. That happens with heaps of millions of long-lived containers (large in-memory caches, forked worker pools that want copy-on-write pages). Below that, `gc.disable()`, custom thresholds and `gc.freeze()` are over-engineering. What always matters is not creating cycles that hold large buffers or resources on a hot path, because their memory is released late instead of at once.

## How it fails
- **Cycles on a hot path:** each request builds a parent ↔ child cycle holding a large buffer → memory is freed only when the collector runs, so peaks are much higher than the live data.
- **Collector disabled "for speed":** `gc.disable()` without a matching manual collection → every cycle leaks until the process dies.
- **Resources released by GC:** files, sockets or locks closed only in `__del__` or by being dropped inside a cycle → they stay open until a collection that may come much later.
- **Huge long-lived heap:** millions of tracked containers → each full collection is a stop-the-world pause that shows up in the latency tail.
- **Tuning blind:** thresholds changed or the collector frozen without measuring GC time → no gain, new leaks.

## Review checklist
- [ ] **Are resources released explicitly, not by GC?** · Applies when: the diff opens files, sockets, subprocesses, locks or executors. · Block if: release depends on the object being collected (`__del__`, dropping the last reference) instead of `with`, `close()` or `try/finally`.
- [ ] **Does a per-request or per-run structure avoid cycles that hold large data?** · Applies when: the diff links objects both ways (parent and child, callbacks capturing `self`) in a long-running process. · Block if: the cycle holds large buffers and is created per request or run, with no `weakref` or explicit unlink.
- [ ] **Is GC tuning backed by a measurement?** · Applies when: the diff calls `gc.disable`, `gc.set_threshold`, `gc.freeze` or `gc.collect`. · Block if: there is no measurement of GC time or pause, or the collector is disabled without a guaranteed re-enable or manual collection.

## In the factory
- `factory/` has no `gc`, `__del__` or `weakref` use: the adapter runs on CPython 3.11's default collector, thresholds `(700, 10, 10)`. Right.
- `factory/intake/webhook_adapter.py`: resources are released explicitly (`with` blocks for files and the `/command/data` executor, `subprocess.run` for git and gh), not left to the collector. Right.
- The adapter's heap is small: a full collection in a process holding it, FastAPI and pytest takes about 6 ms (proof below). Pauses cannot matter at one operator's load.
- Not applicable at today's load: threshold tuning, `gc.freeze()`, and pause monitoring.

## Proof
`pytest -s knowledge/systems/proofs/042_gc.py` (Python 3.11; C uses the adapter's real module through `tests/test_adapter.py`'s fixture):
```
A  gc disabled, 2,000 dropped cycles still held: 191 MiB; gc.collect() found 3998 objects; now 0.1 MiB
B    100,000 tracked dicts alive: full gc.collect() pause     7.3 ms
B  1,000,000 tracked dicts alive: full gc.collect() pause    13.2 ms
B  3,000,000 tracked dicts alive: full gc.collect() pause    26.6 ms
C  process holding the adapter (+FastAPI, httpx, pytest): 65,170 tracked objects, full collection 6.1 ms; thresholds (700, 10, 10)
```
A: refcounting alone never frees a cycle; the collector does. B: the full pause grows with the live tracked heap.

## Related
041-memory-leaks.md, 043-thread-safety.md, 091-latency.md

## Sources
- "Garbage collector design", CPython InternalDocs: https://github.com/python/cpython/blob/main/InternalDocs/garbage_collector.md
- "gc: Garbage Collector interface", Python documentation: https://docs.python.org/3/library/gc.html
