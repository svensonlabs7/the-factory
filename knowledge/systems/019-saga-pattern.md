# 19. Saga Pattern

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)compensat|\bsaga\b|_push\(|gh pr create`

## What it is
A saga replaces one long or distributed transaction with a sequence of local transactions T1 … Tn, each committed on its own, each paired with a compensating transaction C1 … Cn that semantically undoes it. Garcia-Molina and Salem (1987) defined the guarantee: either T1 … Tn all run, or T1 … Tj followed by Cj … C1. A compensation "undoes, from a semantic point of view" what its step did (cancel a reservation, refund a charge). It does not restore the old bytes.

The cost is isolation. The paper notes that when a compensation runs, "no effort is made to notify or abort transactions that might have seen the results of Ti", so other readers can act on intermediate states. Richardson's catalogue lists the practical rules:
- each step must atomically update its store and emit its next message (with an outbox);
- coordination is either choreography (services react to events) or orchestration (one coordinator issues commands);
- missing isolation needs countermeasures, such as a semantic lock: a `PENDING` status until the saga completes.

A saga also needs a durable log of which steps completed, so a crashed coordinator can resume or compensate. Compensations must be retried until they succeed, so they must be idempotent.

## When it is worth it
A saga is worth it when one business operation spans services or stores that cannot share a transaction, takes long enough that holding locks across it is unacceptable, and each step has a meaningful undo. Use orchestration when the flow has more than a couple of steps, so it stays visible (017-event-driven-architecture.md). Steps that cannot be undone (an email sent, a PR merged) go last, or get a human or forward-recovery path. When all the data lives in one database, a local transaction is simpler and stronger than a saga.

## How it fails
- **No durable saga log:** the coordinator crashes mid-saga → completed steps are orphaned (reservations held, cards charged), and recovery cannot know what to compensate (proof B).
- **Compensation not retried, or not idempotent:** a transient failure in the undo leaves a half-compensated state, or a retried undo refunds twice.
- **Dirty reads of intermediate state:** another process sees a step's result as final and acts on it (emails a confirmation) before it is compensated (proof C).
- **Irreversible step in the middle:** a step that cannot be compensated runs before a step that can fail → the saga cannot roll back.
- **Compensation that restores old values:** "set seats back to 5" instead of "release one seat" overwrites other transactions' changes made in between.
- **Choreography sprawl:** with many steps reacting to events, nobody can see where a saga is stuck.

## Review checklist
- [ ] **Does every step that can be followed by a failure have a compensation?** · Applies when: the diff implements a multi-step operation across services or stores. · Block if: a step that can be followed by a failing step has no compensating action, and is not explicitly left for human or forward recovery.
- [ ] **Is saga progress durable before the next step runs?** · Applies when: the diff adds or changes a saga coordinator. · Block if: completed steps are recorded only in memory, so a crash loses what needs compensating or resuming.
- [ ] **Are compensations retried and idempotent?** · Applies when: the diff adds a compensating action. · Block if: a transient failure aborts the compensation, or running it twice repeats the effect (a double refund).
- [ ] **Can others act on a step's result before the saga finishes?** · Applies when: a saga step writes state that other components read. · Block if: the state looks final (`CONFIRMED`) during the saga, with no semantic lock or pending status.
- [ ] **Are irreversible steps last?** · Applies when: the diff orders saga steps. · Block if: a step that cannot be undone (an email, a payout, a merge, a publish) runs before steps that can still fail.

## In the factory
- A run is an orchestrated saga: queue, build round, push, open PR, wait for the gate, fix rounds, finish (`_run_agent`, `factory/intake/webhook_adapter.py:495`). It has a durable saga log, the run record and the action log, written after each step (018-distributed-transactions.md). Right.
- It deliberately has no compensations. A failed or blocked run leaves its branch and PR open, and HEARTBEAT reports it (`last_pr_blocked`, `:408`). The PR is the evidence a human needs, and the irreversible step, the merge, belongs to the human or to auto-merge after the gate. That is forward recovery by a person, which is the right choice when the "undo" would destroy the evidence. Right.
- The PR's open state during fix rounds acts as a semantic lock against merging. Required checks fail on a BLOCK, so the PR cannot merge until a later head passes the gate.
- The saga cannot resume after a crash: `_recover` closes in-flight runs as `error` instead of resuming or compensating. That is already recorded (054-rolling-deployments.md, 015-message-queues.md, and the Idempotency row).
- Not applicable at today's load: compensation frameworks, choreographed sagas and saga orchestration engines.

## Proof
`python3.11 -I knowledge/systems/proofs/019_saga.py` runs a trip-booking saga across three SQLite files (flight, hotel, card), with compensations:
```
A  card declined: saga compensated; left reserved {'flight': 0, 'hotel': 0, 'card': 0}
B  crash after 2 steps, no saga log    : recovery found []; left reserved {'flight': 1, 'hotel': 1, 'card': 0}
B  crash after 2 steps, durable saga log: recovery found ['flight', 'hotel']; left reserved {'flight': 0, 'hotel': 0, 'card': 0}
C  no semantic lock: reader saw CONFIRMED, acted on a booking that was cancelled: True
C  semantic lock   : reader saw PENDING, acted on a booking that was cancelled: False
D  compensation fails twice, then succeeds: saga compensated; left reserved {'flight': 0, 'hotel': 0, 'card': 0}; cancelling again: no-op
```

## Related
018-distributed-transactions.md, 017-event-driven-architecture.md, 014-idempotency.md, 015-message-queues.md, 012-retries.md, 054-rolling-deployments.md

## Sources
- Hector Garcia-Molina and Kenneth Salem, "Sagas", SIGMOD 1987: https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf
- "Pattern: Saga", Chris Richardson, microservices.io: https://microservices.io/patterns/data/saga.html
