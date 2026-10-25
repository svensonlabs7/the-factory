# 33. Leader Election

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)\bleader|\blease\b|election|singleton|_recover\b|flock`

## What it is
Leader election picks one node to do work that must not be done twice at once: coordinate writes, run a scheduler, own a queue. The others stand by and take over if it fails.

Raft does it with numbered terms:
- a follower that hears no heartbeat within its election timeout becomes a candidate, increments the term and asks for votes;
- a candidate with a majority leads that term;
- each server votes at most once per term, so there is at most one leader per term.

Without care, several nodes time out together, split the votes, and retry forever. Raft makes split votes rare with randomized timeouts ("chosen randomly from a fixed interval (e.g., 150–300ms)") so "in most cases only a single server will time out".

The hard part is the old leader. Amazon's Builders' Library calls leases with heartbeats the practical approach, and names the danger: a leader paused by GC or a slow network keeps believing it holds an expired lease. "There can be either zero leaders or two leaders during failures." The defences:
- check leadership right before acting;
- make the store reject writes from old terms (fencing, 038-distributed-locks.md);
- make the work idempotent, so a brief double leader does no harm.

## When it is worth it
Election is worth it when one of several replicas must act alone and failover must be automatic: schedulers, primaries, partition owners, lock services. Use an existing implementation (etcd, ZooKeeper, a database lease, Kubernetes `Lease`), never a hand-rolled one. On a single host, the operating system already elects: one process holding an exclusive file lock or a bound port, released when the process dies. For one process run by a supervisor, "election" is just a single-instance guard. Building consensus for it is over-engineering.

## How it fails
- **Endless split votes:** identical election timeouts → every node becomes a candidate together, and no term ever gets a majority (proof A).
- **Two leaders:** a paused or partitioned leader resumes and acts on an expired lease → duplicate work or conflicting writes, unless fencing tokens reject it.
- **Leader flapping:** timeouts shorter than ordinary pauses (GC, load) → constant re-elections, each one a brief outage.
- **No leader for too long:** a timeout set too long after a crash → work stalls while everyone waits.
- **Leadership without exclusivity on the resource:** the leader "owns" the work, but the store accepts writes from anyone → an old leader's writes still land.
- **Hand-rolled election:** subtle races in "check, then claim" logic, the same bug as 039-race-conditions.md.

## Review checklist
- [ ] **Is there exactly one actor for work that must not run twice?** · Applies when: the diff adds a singleton job, scheduler, queue consumer or startup recovery that assumes it is alone. · Block if: nothing guarantees a single instance (election, lease, OS lock, single-replica deployment), and two copies would conflict.
- [ ] **Can a stale leader still act?** · Applies when: the diff uses a lease or election to grant exclusive work. · Block if: the leader does not recheck leadership right before side effects, and the resource does not reject old terms or tokens.
- [ ] **Are election timeouts randomized and longer than normal pauses?** · Applies when: the diff configures heartbeats or election timeouts. · Block if: timeouts are identical across nodes, or shorter than routine GC and network pauses.
- [ ] **Is the work safe if leadership briefly doubles or lapses?** · Applies when: the diff hands work to an elected leader. · Block if: a duplicate run, or a gap of one timeout, corrupts state instead of being absorbed by idempotency.
- [ ] **Is a proven implementation used?** · Applies when: the diff adds election or lease logic. · Block if: it is hand-rolled instead of using the platform's lease, an OS lock, or a coordination service.

## In the factory
- There is one adapter and no election: a single launchd job is the leader by construction (`factory/intake/com.svenson.factory-intake.plist`), with one run worker (`factory/intake/webhook_adapter.py:151`).
- What is missing is the single-instance guard. A second copy runs `_recover` and acts as a second leader even when its bind fails (the medium Blue-Green row in GAPS.md, from 052-blue-green-deployment.md).
- The proposed fix is a local OS-level election: an exclusive `fcntl.flock` taken at import, before `_recover`. Proof B shows it behaves the way the Builders' Library asks:
  - a killed holder releases the lock at once, with no timeout to wait out;
  - a frozen holder keeps it, so no second leader can appear while the first could still wake up.
- Not applicable at today's load: Raft, leases, fencing tokens and coordination services. There is one host and one process.

## Proof
`python3.11 -I knowledge/systems/proofs/033_leader.py`. A simulates 5 nodes with a 10 ms vote round trip over 1,000 seeded trials: a node that times out within one round trip of the first also becomes a candidate, and the votes split. B uses real processes contending for `fcntl.flock` on one file:
```
A  fixed 150 ms          : leader elected in 0/1000 trials; mean rounds nan
A  randomized 150-300 ms : leader elected in 1000/1000 trials; mean rounds 1.43
B  process A: leader; process B now: follower
B  A frozen (SIGSTOP) for 0.5 s; B tries: follower  (no second leader while A could still wake up)
B  A killed (SIGKILL); B tries: leader after 9 ms, no timeout to wait out
```
The 9 ms includes starting B's Python process.

## Related
038-distributed-locks.md, 052-blue-green-deployment.md, 037-pessimistic-locking.md, 095-network-partitions.md, 096-clock-skew.md, 085-failover.md

## Sources
- Diego Ongaro and John Ousterhout, "In Search of an Understandable Consensus Algorithm (Raft)", section 5.2 (Leader election): https://raft.github.io/raft.pdf
- "Leader election in distributed systems", Amazon Builders' Library: https://builder.aws.com/content/3Ev0vH0hfkcUizISUWYTvHibtcp/leader-election-in-distributed-systems
