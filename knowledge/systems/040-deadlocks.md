# 40. Deadlocks

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

## What it is
A deadlock is a set of actors each waiting for something another one holds, so none can ever proceed. It needs four conditions at once (Coffman's conditions):
1. exclusive resources;
2. holding while waiting;
3. no forced release;
4. a cycle of waits.

Break any one and deadlock is impossible. In practice:
- acquire multiple locks in one global order (breaks the cycle);
- never wait while holding a lock if you can help it;
- use timeouts on waits, so a deadlock becomes an error instead of a hang;
- keep critical sections small and free of callbacks.

Common real shapes:
- two locks taken in opposite orders;
- a non-reentrant lock re-acquired by its own holder;
- a bounded pool whose tasks wait for other tasks in the same pool;
- a parent waiting on a child that is blocked writing to a full pipe (044-backpressure.md);
- database transactions updating rows in different orders.

Databases such as PostgreSQL detect deadlocks and abort one transaction. Most application code does not, and simply hangs.

## When it is worth it
It matters whenever code holds a lock, a transaction or a pool slot while waiting for something else. A design with one lock and short, callback-free critical sections cannot deadlock on locks, which is the cheapest solution. Lock-ordering hierarchies, deadlock detectors and wait-for graphs are for systems with many locks and contended resources.

## How it fails
- **Opposite lock order:** thread A holds X and wants Y, thread B holds Y and wants X → both wait forever, and the service hangs with no error.
- **Re-entering a non-reentrant lock:** a function that holds a lock calls a helper that takes the same lock → it waits on itself.
- **Pool starvation:** a task in a pool of N waits on a task submitted to the same pool, and with N tasks doing this no slot is free (with N = 1, immediately).
- **Waiting on a pipe or child while holding the reader:** the parent waits for the child to exit, and the child waits for the parent to read.
- **Callbacks under a lock:** code under the lock calls user code or logging that, directly or not, needs the same lock.
- **No timeout:** the deadlock is indistinguishable from slowness until someone notices.

## Review checklist
- [ ] **Do multiple locks follow one documented order?** · Applies when: the diff takes more than one lock, or a lock plus a transaction or file lock, in the same code path. · Block if: the acquisition order is not the same everywhere, or not written down.
- [ ] **Is the critical section free of re-entry and callbacks?** · Applies when: the diff adds code that runs while holding a lock. · Block if: it calls a function that can take the same non-reentrant lock, or calls user callbacks, network or subprocesses while holding it.
- [ ] **Does any task wait on work in its own bounded pool?** · Applies when: the diff submits to an executor or pool from code that may itself run in that pool. · Block if: it then waits on the result while the pool's size can be exhausted (always true for one worker).
- [ ] **Do waits that could deadlock have timeouts?** · Applies when: the diff adds a lock acquire, `future.result()`, `process.wait()` or a blocking queue get across threads or processes. · Block if: the wait has no timeout and no proof that a cycle is impossible.

## In the factory
- `factory/intake/webhook_adapter.py:532-547,634-635`: there is one lock, `HEARTBEAT_LOCK`. Under it the code only reads the file, runs regex substitutions, logs a warning and writes atomically. There are no nested acquisitions, callbacks or I/O waits, so no lock cycle is possible. Right.
- `factory/intake/webhook_adapter.py:151,612`: `RUN_EXECUTOR` has one worker, and nothing waits on its futures (grep finds no `.result()`). `/trigger` only submits. Right, but a run must never submit to and wait on `RUN_EXECUTOR` (proof C).
- `factory/intake/webhook_adapter.py:430-435`: the agent subprocess writes to a file, not a pipe, and `_run` uses `capture_output` (`communicate()`), so there is no pipe deadlock (044-backpressure.md). Right.
- `HEARTBEAT_LOCK` is a plain `Lock` (proof B). That is safe today, and a hazard if `_set_heartbeat` is ever called from code already holding it. The checklist item above catches that.
- Not applicable at today's load: lock hierarchies and deadlock detection. There is one lock and one worker.

## Proof
`pytest -s scratchpad/mastery/040_deadlocks.py` (B uses the adapter's real `HEARTBEAT_LOCK` and `_set_heartbeat` through `tests/test_adapter.py`'s fixture). Every wait has a timeout:
```
A  opposite order: [('t0', False), ('t1', False)]   (False = gave up after 1 s: deadlocked)
A  same order:     [('t0', True), ('t1', True)]
B  holding HEARTBEAT_LOCK, then calling _set_heartbeat: finished = False (blocked on itself)
B  lock type: lock; an RLock would let the same thread re-enter
C  outer waited 1 s for inner; inner can never start: the only worker is outer
```

## Related
039-race-conditions.md, 043-thread-safety.md, 044-backpressure.md, 037-pessimistic-locking.md, 011-timeouts.md

## Sources
- "Explicit Locking: Deadlocks", PostgreSQL documentation: https://www.postgresql.org/docs/current/explicit-locking.html
- "threading: Lock Objects and RLock Objects", Python documentation: https://docs.python.org/3/library/threading.html
