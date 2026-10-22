# 35. Eventual Consistency

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

## What it is
Eventual consistency promises only that if writes stop, all replicas will converge on the same value. Until then, a read may return an older value. Vogels calls the gap the inconsistency window, and frames it with N replicas, W of them written before a write returns, and R of them read:
- with W + R > N, every read overlaps the latest write;
- with W + R ≤ N, a read can miss it.

DynamoDB makes eventually consistent reads the default. They "might not reflect the results of a recently completed write", and "if you repeat your read request after a short time, the response should eventually return the more recent item". Strongly consistent reads are an option at twice the cost.

Two things are easy to forget:
- **Converging is not the same as being correct.** If concurrent writes are merged by last-write-wins, the replicas agree on a value that silently dropped writes. Data types designed to merge (CRDTs such as grow-only counters and sets) or application-level merge rules keep every write.
- **Clients need session guarantees on top:** read-your-writes and monotonic reads (029-read-replicas.md).

## When it is worth it
Eventual consistency is worth accepting where availability and latency matter more than seeing the latest write at once: feeds, counters, caches, search indexes, dashboards, cross-region replicas. It needs a stated staleness bound, a merge rule for concurrent writes, and session guarantees where users would notice. It is the wrong default for invariants (balances, uniqueness, permissions, state machines), which need strong reads or a single writer. Caches are a form of eventual consistency too: every TTL is a staleness bound, and every "never expires" entry is a claim that the value cannot change.

## How it fails
- **Read misses a just-completed write:** with W + R ≤ N, a read 10 ms after a write sees it only about a third of the time (proof A) → the user's change "disappears".
- **Converged but wrong:** concurrent increments or edits are merged by last-write-wins → the replicas agree, and half the updates are gone (proof B).
- **Unbounded staleness:** an entry cached "forever" because its value "cannot change", and then it does → the stale value never heals (proof C).
- **Invariant enforced on stale data:** "is the username free?" or "is the balance enough?" answered from a lagging replica → duplicates or overdrafts.
- **No convergence:** replicas without anti-entropy or repair diverge permanently after a missed message.
- **Clock-based ordering:** last-write-wins by wall clock across machines → skew decides which write survives (096-clock-skew.md).

## Review checklist
- [ ] **Is the staleness bound stated for each eventually consistent read?** · Applies when: the diff reads from a cache, replica, index or eventually consistent API. · Block if: there is no TTL, version check or documented window, and the reader cannot tolerate unbounded staleness.
- [ ] **Is "never expires" true?** · Applies when: the diff caches a value indefinitely because it is final. · Block if: the source can still change it (a reopenable state, an editable record, a mutable tag).
- [ ] **Do concurrent writes merge without losing data?** · Applies when: the diff lets several replicas or clients write the same item without coordination. · Block if: they are merged by last-write-wins (or wall-clock order) on data where every write counts (counters, sets, logs, money).
- [ ] **Are invariants checked against strongly consistent state?** · Applies when: the diff enforces uniqueness, limits, balances or permissions. · Block if: the check reads an eventually consistent source.
- [ ] **Is eventual consistency acceptable here at all?** · Applies when: the diff moves a read from a primary or strong read to a replica or cache. · Block if: the read feeds a decision or display that users rely on being current, with no fallback.

## In the factory
- GitHub is the factory's eventually consistent dependency. The adapter waits for the pushed head to appear before reading checks (032-replication.md), with the two-read caveat in 029-read-replicas.md.
- The dashboard's PR cache is a stated staleness bound: open PRs are reused for 60 s (`PR_CACHE_TTL`, `factory/intake/webhook_adapter.py:646`). Right.
- Gap (low): `_pr` (`:658-672`) keeps merged and closed PRs "for good", but CLOSED is not final, because a closed PR can be reopened (`gh pr reopen`). After a reopen, the dashboard keeps showing CLOSED until the adapter restarts, whatever the TTL (proof C). MERGED is final; CLOSED should be cached like OPEN (see GAPS.md).
- The run record (`meta.json`) and HEARTBEAT are written one after the other, so a reader can briefly see them disagree. The record is the source of truth (017-event-driven-architecture.md).
- Not applicable at today's load: quorums, CRDTs and anti-entropy. There is one writer.

## Proof
`pytest -s knowledge/systems/proofs/035_eventual.py` (Python 3.11). A is N = 3 replicas with seeded propagation delays of 0 to 100 ms over 10,000 trials. C is the real `_pr` through `tests/test_adapter.py`'s fixture:
```
A  W=1 R=1 (W+R<=3): read 10 ms after the write sees it 34.4% of the time
A  W=2 R=2 (W+R>3): read 10 ms after the write sees it 100.0% of the time
B  10 increments across a partition: last-write-wins converges on 5; grow-only counter converges on 10
C  PR seen CLOSED, then reopened on GitHub: dashboard after the TTL says 'CLOSED'
```

## Related
032-replication.md, 029-read-replicas.md, 034-cap-theorem.md, 096-clock-skew.md, 002-caching.md, 017-event-driven-architecture.md

## Sources
- "Eventually Consistent - Revisited" (N, W, R; inconsistency window; session guarantees), Werner Vogels: https://www.allthingsdistributed.com/2008/12/eventually_consistent.html
- "DynamoDB read consistency", Amazon DynamoDB Developer Guide: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html
