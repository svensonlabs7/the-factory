# 38. Distributed Locks

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\bredis\b|redlock|distributed.?lock|lock.?service`

## What it is
A distributed lock gives one process at a time, across machines, the right to act on a shared resource. Implementations range from a single Redis key (`SET key token NX PX ttl`, released only if the token still matches) and Redlock (a majority of independent Redis nodes) to consensus systems (ZooKeeper, etcd) and database rows.

All of them hand out leases that expire, so a crashed holder cannot block others forever. The catch, from Kleppmann: a holder can pause (GC, a VM freeze, a network stall) past its lease and wake up still believing it holds the lock, while another process already does. Checking the time before writing does not help. The fix is a fencing token, a number that increases with every grant. The protected storage rejects any write whose token is lower than one it has already seen.

First ask what the lock is for:
- **Efficiency** (avoid duplicate work): a simple single-node lock is fine.
- **Correctness** (avoid corrupt data): you need fencing, enforced by the resource itself, and a lock service with real consensus.

## When it is worth it
Only when several machines must coordinate on a shared resource and a queue, partitioning or a database constraint cannot do it more simply. On one machine, a process-level lock, a bound port or a single worker is simpler and stronger. Even with many machines, prefer designs where the storage itself enforces ordering (compare-and-swap, conditional writes, `SELECT ... FOR UPDATE`) over a separate lock service.

## How it fails
- **Lease expires mid-work:** the holder pauses, its lease expires, another client takes the lock, and both write → the stale write overwrites the new one.
- **No fencing at the resource:** the lock service is correct, but the storage does not check tokens, so mutual exclusion is only advisory.
- **Releasing someone else's lock:** an unconditional `DEL` after your lease expired deletes the next holder's lock.
- **Replication lag in the lock store:** the lock is written to a primary that fails over before replicating, so two clients hold it.
- **Clock jumps:** TTLs measured on wall clocks shrink or grow when clocks are adjusted (see 096-clock-skew.md).
- **Using a correctness lock where an efficiency lock was enough:** a five-node Redlock cluster to prevent duplicate emails is complexity without benefit.

## Review checklist
- [ ] **Is a distributed lock needed at all?** · Applies when: the diff adds a lock service, a Redis or etcd lock, or a lease. · Block if: the coordinating actors run on one machine, or the shared store can enforce the rule itself (a conditional write, a unique constraint, a compare-and-swap). · tripwire
- [ ] **For correctness locks, does the resource check a fencing token?** · Applies when: the lock protects data whose corruption matters. · Block if: writes to the protected resource do not carry and check an increasing token or version.
- [ ] **Is release conditional on ownership?** · Applies when: the diff releases a lock in a shared store. · Block if: release deletes the key unconditionally instead of only when the stored token is still this holder's.
- [ ] **Is work bounded by the lease?** · Applies when: the diff does work while holding a lease. · Block if: the work can outlast the lease with no renewal or fencing, and nothing stops a stale holder from writing.

## In the factory
- One host, one adapter. `RUN_EXECUTOR` (`max_workers=1`) gives one run at a time exclusive use of the plan and repo, and no distributed lock is needed. Right. The bound port `127.0.0.1:7654` is not a single-instance lock (corrected in review 50): a second start's import runs `_recover` before the bind fails (052-blue-green-deployment.md). A local `flock` at import is the fix, not a distributed lock.
- `factory/intake/webhook_adapter.py:350`: a non-forced `git push` is a compare-and-swap on the remote branch, so GitHub itself fences stale writers. If a stale actor pushes after the branch moved, it is rejected (036-optimistic-locking.md). That is fencing enforced by the resource.
- `.github/workflows/*.yml`: no `concurrency:` groups. That is fine, because the adapter pushes a new head only after every check on the previous head has finished, so gate runs for one PR do not overlap.
- If the factory ever runs workers on several hosts (multi-repo builds), coordinate through a queue with leases, plus conditional writes at the resource (git push without force, or a database row with a version), not through a Redis lock alone.
- Not applicable at today's load: Redis or Redlock, ZooKeeper or etcd, lease renewal.

## Proof
`python3 -I knowledge/systems/proofs/038_fencing.py`, Kleppmann's scenario in simulated time. 10 s leases; client 1 takes token 33 and pauses 15 s; client 2 takes token 34:
```
A  lock only, no fencing : client2 token 34 wrote "client2's data"; client1 token 33 wrote "client1's stale data"; final value "client1's stale data"
B  with fencing tokens   : client2 token 34 wrote "client2's data"; client1 token 33 REJECTED (already saw 34); final value "client2's data"
```
The git equivalent, a stale push rejected because the branch moved on, is proven with real git in 036-optimistic-locking.md.

## Related
036-optimistic-locking.md, 037-pessimistic-locking.md, 033-leader-election.md, 096-clock-skew.md, 039-race-conditions.md, 052-blue-green-deployment.md

## Sources
- Martin Kleppmann, "How to do distributed locking": https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
- "Distributed Locks with Redis", Redis documentation: https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
