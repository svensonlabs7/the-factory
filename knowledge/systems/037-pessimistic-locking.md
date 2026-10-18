# 37. Pessimistic Locking

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

## What it is
Pessimistic locking prevents conflicts by taking an exclusive lock before touching shared data, so nobody else can change it until you release it. Examples: a mutex, `SELECT ... FOR UPDATE`, a database write lock, a file lock, a single-worker queue, or a port only one process can bind. It never wastes finished work on a conflict, because there is no conflict. The cost is waiting: every other actor waits for as long as the lock is held. So the rules are:
- hold locks for as short a time as possible;
- never hold them across slow I/O or user think-time;
- always put a timeout on the wait (`NOWAIT`, `lock_timeout`, `acquire(timeout=)`);
- for job queues, use `SKIP LOCKED`, so workers take the next free item instead of queueing behind a locked one.

Choose pessimistic over optimistic (036-optimistic-locking.md) when conflicts are frequent, or when redoing the work is expensive.

## When it is worth it
It is worth it for short critical sections over in-process state, for resources where a conflict would waste expensive work (a build, a payment, a long edit), and for queues with several consumers (`FOR UPDATE SKIP LOCKED`). Cross-machine locks (038-distributed-locks.md), lock managers and lease renewal are for multiple hosts. On one process, a mutex or a single worker is enough.

## How it fails
- **Lock held across slow work:** a request holds a row or file lock during a network call → every other request waits, and latency becomes the slowest holder's duration.
- **No wait timeout:** a stuck holder means everyone else hangs forever, which is indistinguishable from an outage.
- **Lock taken too broadly:** a table lock where a row lock would do, or one global mutex for unrelated data → concurrency collapses.
- **Stale lock after a crash:** a lock file or held row outlives its owner → nobody can proceed until someone clears it by hand.
- **Lock scope narrower than the sharing:** an in-process mutex protects data that a second process also writes → no protection at all.
- **Deadlock from multiple locks:** see 040-deadlocks.md.

## Review checklist
- [ ] **Is the lock held only for the critical section?** · Applies when: the diff takes a lock, a `FOR UPDATE`, or a file or table lock. · Block if: network calls, subprocesses, sleeps or user interaction happen while it is held.
- [ ] **Does the wait have a timeout or a skip option?** · Applies when: the diff waits for a lock another actor can hold. · Block if: the wait is unbounded with no `NOWAIT`, `lock_timeout`, `acquire(timeout=)` or `SKIP LOCKED`.
- [ ] **Does the lock's scope match who shares the data?** · Applies when: the diff protects data that more than one process or host can write. · Block if: it uses an in-process lock (`threading.Lock`) for data shared across processes.
- [ ] **Can the lock outlive its owner?** · Applies when: the diff adds a lock that persists outside the process (lock file, row flag, lease). · Block if: a crashed owner leaves it held, with no expiry or stale-owner check.

## In the factory
- `factory/intake/webhook_adapter.py:532-547`: `HEARTBEAT_LOCK` is a mutex around the HEARTBEAT read-modify-write. The critical section is pure local file work: a median hold of 0.16 ms and a maximum of 2.76 ms over 500 updates. Right.
- `factory/intake/webhook_adapter.py:151`: `RUN_EXECUTOR` has `max_workers=1`, which serialises runs and gives each one exclusive use of the Claude plan quota and the origin repo. It is pessimistic by design, because conflicting builds are expensive. Right.
- `factory/intake/com.svenson.factory-intake.plist`: the adapter binds `127.0.0.1:7654`, so a second instance on that port fails with `EADDRINUSE`. The port works as a single-instance lock, and releases itself when the process dies. Right.
- Limitation, not observed: `HEARTBEAT_LOCK` is per-process. A second adapter on another port with the same `FACTORY_ROOT` (a manual debug run, say) would share HEARTBEAT and the run metas without any lock between them. Run debug instances against a temporary `FACTORY_ROOT`, as the tests do.
- Not applicable at today's load: `FOR UPDATE` and `SKIP LOCKED`. There is no database, and one worker.

## Proof
`pytest -s scratchpad/mastery/037_pessimistic.py` (B uses the adapter's real `_set_heartbeat` and `HEARTBEAT_LOCK` through `tests/test_adapter.py`'s fixture; C tests the live adapter's port):
```
A  writer 2 (timeout 0.5 s): database is locked after 0.6 s
A  writer 2 (timeout 5 s): succeeded after 1.4 s, once writer 1 committed
B  HEARTBEAT_LOCK hold per _set_heartbeat (500 calls): median 0.16 ms, max 2.76 ms
C  second instance binding 127.0.0.1:7654: EADDRINUSE (Address already in use)
```
In A, writer 1 held SQLite's write lock (`BEGIN IMMEDIATE`) through 2 s of slow work. Writer 2 either gave up or waited out the hold.

## Related
036-optimistic-locking.md, 040-deadlocks.md, 038-distributed-locks.md, 039-race-conditions.md, 015-message-queues.md

## Sources
- Martin Fowler, "Pessimistic Offline Lock", Patterns of Enterprise Application Architecture: https://martinfowler.com/eaaCatalog/pessimisticOfflineLock.html
- "SELECT: The Locking Clause", PostgreSQL documentation: https://www.postgresql.org/docs/current/sql-select.html
