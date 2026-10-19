# 32. Replication

Track: G. Data · Status: proven · Updated: 2026-10-19

## What it is
Replication keeps copies of the same data on several nodes, for durability (survive losing one), availability (fail over), and read scaling (serve reads from copies). The common shape is leader/follower: the leader accepts writes and ships its change log, and followers apply it.

The central choice is when a write counts as done:
- **Asynchronous:** the leader acknowledges after its own commit. That is fast, but Postgres warns that "if the primary server crashes then some transactions that were committed may not have been replicated to the standby server, causing data loss", in proportion to the replication delay.
- **Synchronous:** the leader waits for a follower's confirmation. Nothing acknowledged is lost unless both fail, but every commit pays at least a round trip, and locks are held while it waits.

Postgres lets the guarantee vary per transaction. `remote_apply` waits until the standby has replayed the write, which makes it visible to reads there.

Followers lag, so a client that writes and then reads from a follower may not see its own write. That is a read-your-writes violation. The fixes: read from the leader, or wait until the follower has reached the write's log position.

## When it is worth it
Replication is worth it when losing a node's data or its availability is unacceptable, or when reads outgrow one node. Choose sync for data whose loss after acknowledgement is unacceptable (payments, orders), and async for data that can lose its last second (chat, metrics), and say which. Any read from a replica needs a stated staleness tolerance. For a single host with small, rebuildable state, replication is over-engineering. Backups (084-backups.md) and a known restore are the proportionate defence.

## How it fails
- **Async failover loses acknowledged writes:** the leader dies with unshipped changes, a follower is promoted → writes the client was told succeeded are gone.
- **Stale read after write:** a user saves, the next page reads a lagging replica → their change "disappeared", or a check passes on old data.
- **Sync replication stalls writes:** the synchronous follower is slow or down → every commit waits, and the primary is effectively down, unless there is a quorum or a fallback.
- **Split brain:** two nodes both believe they are the leader after a partition → divergent writes (038-distributed-locks.md, 085-failover.md).
- **Lag grows unnoticed:** a follower falls minutes behind, and nothing alerts until a failover loses minutes of data.
- **Replica treated as a backup:** a bad write or `DROP` replicates instantly, so the copy is just as wrong.

## Review checklist
- [ ] **Is the durability guarantee stated for each write path?** · Applies when: the diff configures replication or writes data whose loss after acknowledgement matters. · Block if: acknowledged writes can be lost on failover (async) for data the product treats as committed, with no sync commit or stated loss window.
- [ ] **Does a read that must see a recent write go where it can?** · Applies when: the diff reads from a replica, cache or eventually-consistent API right after a write. · Block if: the read can return state from before the write and nothing checks a version or position, or waits for it.
- [ ] **Is replication lag monitored?** · Applies when: the diff adds a replica or relies on one. · Block if: nothing alerts when lag exceeds what reads or failover can tolerate.
- [ ] **Can a sync follower's failure stop writes?** · Applies when: the diff enables synchronous replication. · Block if: one follower's outage blocks all commits, with no quorum (`ANY n`) or documented fallback.
- [ ] **Is replication justified?** · Applies when: the diff adds replicas. · Block if: the data is small and rebuildable on one host, and a backup with a tested restore would meet the need.

## In the factory
- The factory has no database to replicate. Its one replicated store is git: `_push` copies each run's commits to GitHub, the durable copy (`factory/intake/webhook_adapter.py:338-350`). Work the agent did is safe once pushed, and only the unpushed part of an in-flight run is at risk.
- GitHub's view of a PR lags behind a push, the same read-your-writes problem as a lagging replica. `_gate_results` (`:352-370`) waits until `gh pr view` shows the pushed head before reading checks, so it never acts on a stale head. Right (proof B). The checks themselves come from a second read with no SHA, which can still lag; that is 029-read-replicas.md's gap (corrected in review 70). The tests cover it as `FAKE_STALE` (`tests/test_adapter.py:103-104`).
- Run records, logs and `.env` exist only on the Mac's disk, with no copy anywhere. That is a durability question for 084-backups.md, not a reason to replicate.
- Not applicable at today's load: database replication, read replicas and lag monitoring.

## Proof
`pytest -s scratchpad/mastery/032_replication.py` (Python 3.11). A is leader and follower on two SQLite files, with a shipper thread applying the log 0.2 s behind. B is the real `_gate_results` through `tests/test_adapter.py`'s fixture, with `_run` playing a GitHub that shows the new head on the third look:
```
A  async: 50 writes acknowledged, 14 lost on failover [37, 38, 39]...; ~4 ms added per write
A  sync : 50 writes acknowledged, 0 lost on failover []; ~216 ms added per write
A  read-your-writes on the follower right after the write: False
A  after waiting for the follower to reach the write:     True
B  naive read right after pushing new222: [{'name': 'tests', 'bucket': 'fail'}]  (the previous commit's checks)
B  _gate_results('url', 'new222'):        {'tests': 'pass'}  after 3 looks at the PR head
```
- Async replication lost the 14 writes inside the 0.2 s lag window, all of them acknowledged. Sync lost none, but added the lag to every write.
- A naive read of the PR would have reported the previous commit's failure for a passing push.

## Related
029-read-replicas.md, 035-eventual-consistency.md, 034-cap-theorem.md, 084-backups.md, 085-failover.md, 038-distributed-locks.md, 095-network-partitions.md

## Sources
- "High Availability, Load Balancing, and Replication: Log-Shipping Standby Servers" (streaming and synchronous replication), PostgreSQL documentation: https://www.postgresql.org/docs/current/warm-standby.html
- "Eventually Consistent - Revisited" (read-your-writes, the inconsistency window), Werner Vogels: https://www.allthingsdistributed.com/2008/12/eventually_consistent.html
