# 34. CAP Theorem

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

## What it is
The CAP theorem (Brewer's conjecture, proved by Gilbert and Lynch in 2002) says that when the network partitions, a replicated system cannot give both:
- **Consistency:** atomic, linearizable reads and writes. Every operation "looks as if it were completed at a single instant."
- **Availability:** "every request received by a non-failing node in the system must result in a response."

During a partition, each side must either refuse some requests (CP) or answer them from local state and risk divergence (AP).

Brewer's 2012 retrospective corrects the popular "pick 2 of 3" reading:
- partitions are rare, so a system can be both C and A most of the time;
- the choice applies only while a partition is present or perceived;
- it can be made per operation, per data item or per user, not once per system.

Handling a partition has three steps: detect it, enter a partition mode that limits some operations, and recover afterwards, compensating for what went wrong. Latency is the same trade in disguise: "a partition is a time bound on communication", so every timeout is a decision between waiting (C) and answering (A).

## When it is worth it
Use CAP to choose behaviour, operation by operation, for anything that depends on a remote state or service:
- Which requests must refuse rather than act on possibly stale or divergent data? Money, uniqueness, security decisions, merges.
- Which can answer with what is known? Dashboards, feeds, caches, telemetry.
- How is each side reconciled when the partition heals?

Labelling a whole system "CP" or "AP", or adopting a consensus database to "get C", is the over-engineering version. Most systems need a written choice for a handful of operations.

## How it fails
- **AP by accident for an operation that needed C:** both sides accept writes, and on heal last-write-wins silently drops one side's writes (proof A). Orders, balances or merges are lost with no error.
- **CP by accident for an operation that could be A:** a read-only dashboard or a health page fails whenever a dependency is unreachable, hiding the very information needed during the incident.
- **No partition mode:** the system neither refuses nor marks answers as degraded, so callers cannot tell a fresh answer from a stale one.
- **No recovery plan:** after the heal, divergent replicas are reconciled by whoever writes last, or by hand.
- **"Retry forever" as a design:** an operation that waits indefinitely has chosen C, without anyone saying so.
- **CAP used to justify skipping consistency when no partition exists:** the trade-off only binds during partitions; otherwise latency is the real trade (PACELC).

## Review checklist
- [ ] **Is each operation's partition behaviour chosen?** · Applies when: the diff adds an operation whose result depends on a remote store or service. · Block if: it is unstated, and not evident from the code, whether the operation refuses or answers from local or stale state when the remote is unreachable.
- [ ] **Do operations that need consistency refuse rather than guess?** · Applies when: the diff makes a decision (merge, payment, uniqueness, authorization, gate verdict) from remote state. · Block if: on a timeout or unreachable remote it proceeds on cached, default or partial data.
- [ ] **Do read-only views stay available and say so?** · Applies when: the diff adds a status page, dashboard or report that reads several sources. · Block if: one unreachable source fails the whole view, or stale or missing parts are shown as if fresh.
- [ ] **Is reconciliation after a partition defined?** · Applies when: the diff lets several nodes or sides accept writes independently. · Block if: concurrent writes are merged by implicit last-write-wins on data where losing a write matters.
- [ ] **Is a consensus store justified?** · Applies when: the diff adds Raft or Paxos-based storage or a coordination service. · Block if: a single writer, or a per-operation refuse-or-degrade choice, meets the need.

## In the factory
The factory is one node. Its CAP choices are about its dependency, GitHub, and they are made per operation, as Brewer recommends:
- **Dashboard, available.** `command_data` (`factory/intake/webhook_adapter.py:691-712`) answers with the local run records whatever GitHub's state. `_pr` (`:658-672`) returns `None` for a PR it cannot fetch, "so one bad PR cannot sink the dashboard". The page shows no PR state rather than guessing (proof B). Right.
- **Gate verdict, consistent.** `_gate_results` (`:352-370`) raises when GitHub is unreachable, and never assumes a pass. The run ends as `error` instead of merging on a guess. Right.
- **Intake, available.** `/trigger` accepts and queues runs without asking GitHub, and the push and PR wait for the network later.
- The rough edges are elsewhere: the ambiguous PR creation (095-network-partitions.md) and the two-read gate (029-read-replicas.md).
- Not applicable at today's load: quorums, consensus and multi-writer reconciliation. There is one writer.

## Proof
`pytest -s scratchpad/mastery/034_cap.py` (Python 3.11). A is three replicas partitioned {n1, n2} | {n3}, each side taking a write, then healed. B is the real adapter through `tests/test_adapter.py`'s fixture, with every `gh` call failing as "no route to host":
```
A  CP: write via n1 -> ok; write via n3 -> rejected (no quorum); after heal every node holds {'order A (majority side)'}
A  AP: write via n1 -> ok; write via n3 -> ok; after heal every node holds {'order B (minority side)'}
B  dashboard read while GitHub is unreachable: HTTP 200, run r1 status 'completed', pr None
B  gate verdict while GitHub is unreachable: raised RuntimeError: dial tcp api.github.com:443: no route to host
```
In AP mode both writes were acknowledged, and the heal silently discarded "order A".

## Related
095-network-partitions.md, 035-eventual-consistency.md, 032-replication.md, 029-read-replicas.md, 033-leader-election.md, 018-distributed-transactions.md

## Sources
- Seth Gilbert and Nancy Lynch, "Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services", SIGACT News 2002: https://users.ece.cmu.edu/~adrian/731-sp04/readings/GL-cap.pdf
- Eric Brewer, "CAP Twelve Years Later: How the 'Rules' Have Changed" (IEEE Computer, 2012; InfoQ copy): https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/
