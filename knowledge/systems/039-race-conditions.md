# 39. Race Conditions

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

## What it is
A race condition is a bug whose outcome depends on the timing of concurrent actors (threads, processes, requests, machines) touching shared state. The classic shapes:
- **Lost update:** two read-modify-write cycles interleave, and one write erases the other.
- **Check-then-act, or time-of-check to time-of-use (TOCTOU):** the state checked changes before it is used.
- **Torn read:** a reader sees a half-written file or record.

The fixes, in order of preference:
1. Do not share the state (give each actor its own).
2. Make the operation atomic (create-if-absent, rename into place, compare-and-swap, a database constraint).
3. Hold a lock around the whole critical section.

Races hide in tests and appear under load or at bad moments, so they are found by reasoning about every shared resource, not by waiting for a failure.

## When it is worth it
Always, for any state touched by more than one thread, process, request handler or machine: files, rows, caches, git refs, temp paths, counters. That includes "shared" things you do not own, such as a repository another tool also writes to. Fine-grained lock-free designs and distributed locks are for contended, high-throughput paths. Most code needs only "one writer per thing" plus atomic writes.

## How it fails
- **Lost update:** two threads read 5, both write 6 → one increment, a payment or a status change is lost.
- **Torn read:** a writer truncates and rewrites a file in place → a concurrent reader gets empty or partial content and crashes or acts on garbage.
- **TOCTOU:** "if the slot is free, take it", where another actor takes it in between → two owners, or a limit exceeded.
- **Shared scratch name:** two writers use the same temp file or ref name → they overwrite each other's intermediate state.
- **Shared global file in a tool:** `FETCH_HEAD`, a lock file or a cache in a repository or directory that another process also uses → you read the other process's result.

## Review checklist
- [ ] **Is every new piece of shared state either single-writer or protected?** · Applies when: the diff adds state touched by more than one thread, process or request (files, dicts, counters, refs, rows). · Block if: two actors can write it with no lock, atomic operation or ownership rule.
- [ ] **Are file writes that others read atomic?** · Applies when: the diff writes a file another thread or process may read at the same time. · Block if: it truncates and rewrites in place instead of writing a temp file and renaming it.
- [ ] **Is check-then-act made atomic?** · Applies when: the diff checks a condition and then acts on it (exists then create, count then admit, read then update). · Block if: another actor can change the condition between the check and the act.
- [ ] **Does the code read its own result, not a shared slot?** · Applies when: the diff runs a tool whose output lands in a shared location (`FETCH_HEAD`, a fixed temp path, a "latest" file). · Block if: it reads that shared slot when it could name its own output (a dedicated ref, a unique temp path).

## In the factory
- `factory/intake/webhook_adapter.py` (`_write_atomic`): meta and HEARTBEAT are written via a temp file and rename, so readers never see a torn file. Each run's meta has one writer (the worker thread). Right.
- `factory/intake/webhook_adapter.py:532-547`: HEARTBEAT read-modify-write is under `HEARTBEAT_LOCK`, which the worker and request handlers share. Right.
- `factory/intake/webhook_adapter.py:227-232`: `_check_capacity` and the new run's meta are written on the event loop with no `await` between them, so two `/trigger` requests cannot both take the last slot. Right.
- `factory/intake/webhook_adapter.py:199-213` (`_replayed`): the atomic `touch(exist_ok=False)`, with `unlink(missing_ok=True)` for pruning. Right.
- `.jsonl` logs are appended with `open("a")` (`O_APPEND`), so concurrent appends of small lines do not interleave. Right.
- Gap (medium): `_push` reads `FETCH_HEAD` in `FACTORY_ROOT`, which defaults to `/Users/labs/projects/the-factory`, the operator's own working copy. Any other `git fetch` there between the adapter's fetch and its `rev-parse` (the operator, an editor's auto-fetch) makes the adapter push someone else's commit (see GAPS.md).
- Not applicable at today's load: distributed locks and lock-free structures. There is one process with one worker thread.

## Proof
`python3 -I scratchpad/mastery/039_races.py`:
```
A  no lock:   counter = 51 (expected 400)     (7 of 8 threads also crashed: ValueError reading '' from a half-written file)
A  with lock: counter = 400 (expected 400)
B  adapter pattern: FETCH_HEAD is the agent's commit = False; someone else's = True
B  own ref:         refs/factory/run1 is the agent's commit = True
```
B runs the adapter's exact `git fetch <clone> main` then `git rev-parse FETCH_HEAD` in scratch repos, with a second fetch placed in the window. `grep` confirms the live plist does not set `FACTORY_ROOT`, so the code default, `/Users/labs/projects/the-factory`, is the adapter's trusted checkout.

## Related
043-thread-safety.md, 040-deadlocks.md, 014-idempotency.md, 038-distributed-locks.md, 036-optimistic-locking.md

## Sources
- "CWE-362: Concurrent Execution using Shared Resource with Improper Synchronization ('Race Condition')", MITRE: https://cwe.mitre.org/data/definitions/362.html
- "CWE-367: Time-of-check Time-of-use (TOCTOU) Race Condition", MITRE: https://cwe.mitre.org/data/definitions/367.html
