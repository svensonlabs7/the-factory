# 29. Read Replicas

Track: G. Data · Status: proven · Updated: 2026-10-19

## What it is
A read replica is a read-only copy of a database that serves queries, so read traffic scales beyond one server's capacity. AWS RDS describes routing queries to replicas to "reduce the load on your primary", plus reporting workloads and serving reads while the primary is busy. Writes still go to the primary, and RDS copies them to replicas asynchronously. Every replica is therefore somewhat behind (RDS reports this as `ReplicaLag`), and each replica is behind by a different amount.

Spreading reads across replicas brings consistency anomalies beyond the plain staleness of one replica (032-replication.md):
- **Monotonic reads:** if consecutive reads land on replicas with different lag, a client can see a value and then an older one. Data appears to go back in time.
- **Inconsistent combined reads:** two reads that belong together, such as an object and its children, or a version and its status, can be served by different replicas at different points in time.

The fixes:
- sticky routing (one replica per session);
- a minimum-version token (a replica answers only once it has applied the version the client last saw, otherwise the primary does);
- reading related data in a single query or snapshot.

## When it is worth it
Read replicas are worth it when reads dominate, the primary's CPU or I/O is the bottleneck, and the reads can tolerate some staleness: reporting, search, feeds, dashboards. They do not help write-bound systems. They add routing logic, lag monitoring and per-query decisions about which reads must go to the primary. Fix slow queries (026-query-optimization.md) and cache hot reads (002-caching.md) before adding a replica. Below the point where one database's read capacity is the measured bottleneck, a replica is over-engineering.

## How it fails
- **Time goes backwards:** round-robin routing across replicas with different lag → a client sees new data, then old data, then new again (proof A).
- **Two-part read from two points in time:** "which version is current" comes from one replica and "what are its results" from another → the answer pairs the new version with the old version's data (proof B).
- **Read-after-write to a replica:** a user's own change is missing on the next page (032-replication.md).
- **A lagging replica stays in rotation:** one replica falls minutes behind, and the load balancer keeps sending it traffic.
- **Writes routed to a replica by mistake:** they fail as read-only, or with a hand-rolled replica, diverge.
- **Replica used for decisions that need fresh data:** stock levels, permissions or uniqueness checks are read from a lagging copy.

## Review checklist
- [ ] **Does each read routed to a replica tolerate its staleness?** · Applies when: the diff sends reads to a replica, follower or eventually-consistent API. · Block if: the read feeds a decision that needs current data (an auth check, an inventory or uniqueness check, a state transition) and has no primary fallback or version check.
- [ ] **Can a session see data go backwards?** · Applies when: the diff load-balances one client's reads across several replicas. · Block if: there is no sticky routing or minimum-version token, and the client can display or act on a newer then an older value.
- [ ] **Are reads that belong together taken from one snapshot?** · Applies when: the diff combines two reads that must agree (a head and its checks, a parent and its children, a count and its rows) from a replicated store or API. · Block if: they are separate requests that can be served at different points in time, with nothing checking they agree (a shared version, ID or SHA).
- [ ] **Is lag monitored, and are lagging replicas removed?** · Applies when: the diff adds replicas to rotation. · Block if: nothing takes a replica out of rotation when its lag exceeds the staleness the reads tolerate.
- [ ] **Are replicas justified?** · Applies when: the diff adds read replicas. · Block if: there is no measured read bottleneck on the primary that query tuning or caching cannot fix.

## In the factory
- There is no database and no replicas. The factory does read from a replicated store it does not control, GitHub, and two of its rules apply there:
  - The single-endpoint lag after a push is handled: `_gate_results` waits for the pushed head (032-replication.md).
  - Gap (low): `_gate_results` (`factory/intake/webhook_adapter.py:352-370`) still combines two separate reads. `gh pr view --json headRefOid` confirms the head, then `gh pr checks --required` reads the checks. The second read carries no commit SHA (its JSON fields are name, state, bucket, link and similar). If it is served by a view that has not caught up with the push, it returns the previous commit's finished checks, and the adapter takes them as the new head's verdict (proof B). In a fix round, that means a spurious BLOCK or a stale PASS. A single snapshot (`gh pr view --json headRefOid,statusCheckRollup`, filtered to the required check names) or a SHA-keyed read (`gh api repos/{owner}/{repo}/commits/{sha}/check-runs`) cannot mix commits (see GAPS.md).
- The dashboard's `_pr` (`:658-672`) already uses the snapshot form: state and checks come from one `gh pr view` call. Right.
- Not applicable at today's load: read replicas, routing, lag monitoring.

## Proof
`pytest -s scratchpad/mastery/029_read_replicas.py` (Python 3.11). A uses a counter that advances every 50 ms, with replicas lagging 60 ms and 400 ms. B is the real `_gate_results` through `tests/test_adapter.py`'s fixture, with `_run` playing a GitHub whose PR-head view has caught up and whose checks view has not:
```
A  round-robin       : version went backwards 20 times in 40 reads
A  sticky            : version went backwards  0 times in 40 reads
A  min-version token : version went backwards  0 times in 40 reads, 38 reads fell back to the primary
B  two reads (head, then checks): _gate_results('url', 'new222') -> {'tests': 'fail'}
B  one snapshot read (head and checks together): head new222 -> {'tests': 'pass'}
```
- A: the token keeps reads monotonic, but a replica that lags far behind becomes useless to that client; 38 of 40 reads went to the primary.
- B: whether GitHub's two endpoints can disagree like this in practice was not observed. The proof shows only that the adapter would accept it if they did.

## Related
032-replication.md, 035-eventual-consistency.md, 026-query-optimization.md, 002-caching.md, 103-semantic-versioning.md

## Sources
- "Working with DB instance read replicas", Amazon RDS User Guide: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html
- "Eventually Consistent - Revisited" (monotonic reads, read-your-writes), Werner Vogels: https://www.allthingsdistributed.com/2008/12/eventually_consistent.html
