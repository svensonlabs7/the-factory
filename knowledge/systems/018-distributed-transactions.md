# 18. Distributed Transactions

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

## What it is
A distributed transaction makes changes in several independent stores (two databases, a database and a queue, a database and an external API) commit or roll back together. The classic protocol is two-phase commit (2PC):
1. **Prepare:** a coordinator asks every participant to prepare. Each one makes its changes durable but undecided, holding its locks, and votes yes or no.
2. **Decide:** the coordinator tells all participants to commit or to roll back.

2PC is atomic, but it blocks. A participant that voted yes cannot decide alone: if the coordinator dies, it keeps its locks until the coordinator, or an operator, returns. Postgres's `PREPARE TRANSACTION` docs say a prepared transaction "continues to hold whatever locks it held", that "it is unwise to leave transactions in the prepared state for a long time", and that the command is meant for "an external transaction manager", not applications.

Pat Helland's position paper argues that large systems mostly do without it: "the performance costs and fragility make them impractical". They keep atomicity within one entity or store, and coordinate between stores with messages, idempotency and compensation (019-saga-pattern.md, the transactional outbox in 017-event-driven-architecture.md).

## When it is worth it
Atomic commit across stores is worth it when one engine already coordinates them cheaply: several files in one SQLite connection, several schemas in one database, XA with a mature transaction manager. It is also worth it when the invariant truly cannot tolerate an intermediate state. Everywhere else, prefer:
- one store per invariant;
- a local transaction plus an outbox for the side effects;
- sagas with compensating steps;
- steps ordered so that each crash point leaves a state the system can recover from.

Hand-rolled 2PC across services is almost always over-engineering with a blocking failure mode.

## How it fails
- **Two independent commits:** the first commits, and the process dies before the second → a debit without the credit, or a record without its side effect (proof A).
- **Coordinator dies after prepare:** participants hold locks with no decision → writes to those rows block or time out until recovery (proof C).
- **Heuristic decisions:** an operator or timeout forces one participant to commit and another to roll back → the atomicity the protocol promised is broken anyway.
- **External side effects inside the "transaction":** an email or API call made before the commit cannot be rolled back.
- **Ambiguous outcome of the last step:** the commit is sent and the reply lost → the caller does not know which state it is in (095-network-partitions.md).
- **Long transactions spanning remote calls:** locks are held across network latency → contention and deadlocks.

## Review checklist
- [ ] **Can a crash between two writes to different stores leave a broken invariant?** · Applies when: the diff writes to two or more stores (databases, files, queues, external APIs) as one logical operation. · Block if: a crash after the first write and before the last leaves a state that nothing detects and repairs (no single transaction, outbox, saga compensation or reconciliation).
- [ ] **Are external side effects ordered after the local commit?** · Applies when: the diff sends an email, message or API call as part of a database change. · Block if: the side effect happens before the local commit and cannot be undone if the commit fails.
- [ ] **Is every prepared or in-doubt state resolved by something?** · Applies when: the diff uses 2PC, `PREPARE TRANSACTION`, XA or a hand-rolled prepare step. · Block if: nothing (a transaction manager, a recovery job, a timeout with a defined decision) resolves participants left prepared by a dead coordinator.
- [ ] **Are locks held across remote calls?** · Applies when: the diff opens a transaction and then makes a network call before committing. · Block if: the call's latency or failure keeps rows locked, with no timeout.
- [ ] **Is a distributed transaction needed at all?** · Applies when: the diff introduces 2PC or XA across services. · Block if: the invariant can live in one store, or be kept by a saga, outbox or idempotent reconciliation.

## In the factory
- A run touches several stores with no transaction across them: the local run record (`meta.json`), HEARTBEAT, the action log, and GitHub (the pushed branch, then the PR). The design orders the steps and records each external effect locally right after it succeeds:
  - `_update(run_id, pr_url=...)` right after `gh pr create` (`factory/intake/webhook_adapter.py:506-507`);
  - `head` after the push (`:338-350`).

  The run record is a progress log, and a crash leaves a known, recoverable state. Right. That is Helland's approach rather than 2PC.
- The crash points that are not cleanly recoverable are already recorded:
  - the ambiguous PR creation (095-network-partitions.md);
  - started runs closed on restart (054-rolling-deployments.md);
  - never-started runs (015-message-queues.md);
  - the record versus HEARTBEAT dual write (017-event-driven-architecture.md).
- GitHub has no leftovers from those crash points today: 16 factory PRs, and 2 remaining `factory/` branches, both with PRs (one merged, one closed). None is orphaned by a failed step (`git ls-remote` and `gh pr list`).
- Not applicable at today's load: 2PC, XA and transaction managers. There is one local store, and GitHub's own atomicity per API call.

## Proof
`python3.11 -I knowledge/systems/proofs/018_dtx.py` uses two SQLite files, moving 100 from A to B:
```
A  two independent commits, crash between them: total 1900 (was 2000)
B  one transaction across both files: after a rollback total 2000, after a commit total 2000, A=900
C  coordinator gone with B prepared: another writer to B -> OperationalError: database is locked
C  after a recovery process rolls B back: total 2000
```
- B: SQLite commits a transaction over attached files atomically, so one engine coordinating both stores keeps the invariant.
- C: a participant left prepared blocks other writers until something decides for the dead coordinator.

## Related
019-saga-pattern.md, 017-event-driven-architecture.md, 014-idempotency.md, 095-network-partitions.md, 030-sharding.md, 037-pessimistic-locking.md

## Sources
- "PREPARE TRANSACTION", PostgreSQL documentation: https://www.postgresql.org/docs/current/sql-prepare-transaction.html
- Pat Helland, "Life beyond Distributed Transactions: an Apostate's Opinion", CIDR 2007: https://www.ics.uci.edu/~cs223/papers/cidr07p15.pdf
