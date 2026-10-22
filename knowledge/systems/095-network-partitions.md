# 95. Network Partitions

Track: H. Distributed systems · Status: proven · Updated: 2026-10-19

## What it is
A network partition is any failure that leaves two parts of a system unable to talk while both keep running: a link down, a switch dropping packets, a firewall change, an overloaded node, or a long GC pause that looks the same from outside. Partitions are routine. Bailis and Kingsbury collected the evidence:
- a Microsoft datacenter study saw about 40.8 link failures a day;
- a new Google cluster's first year typically includes network maintenances that can cost about 30 minutes of connectivity;
- a CENIC WAN study counted 508 isolating partitions over five years.

They are often partial or asymmetric. One case was a NIC that dropped only inbound packets, so the node kept heartbeating while the standby never took over. GitHub's October 2018 incident started with a 43-second partition and ended as 24 hours and 11 minutes of degraded service, because failover wrote to primaries on both coasts.

The core consequence for any remote call is the ambiguous outcome. When a request gets no answer, the caller cannot tell "never arrived" from "done, but the reply was lost." Writes therefore need a way to find out, through an idempotency key or a lookup by natural key, before they are retried or abandoned.

## When it is worth it
Designing for partitions is required for every remote call, not only for distributed databases:
- timeouts on every call, so a partition becomes an error instead of a hang (011-timeouts.md);
- idempotent or checkable writes, so an ambiguous failure can be resolved;
- an explicit choice of what to do while partitioned: reject, queue, or serve stale (034-cap-theorem.md).

Quorums, fencing and partition-tolerant consensus are for systems with several stateful nodes that must agree. One process calling a few external APIs needs only the first two.

## How it fails
- **Ambiguous write treated as failed:** the request succeeded but the reply was lost → the caller reports an error and forgets a resource that exists (an orphaned PR, a charged card), or retries and creates a duplicate.
- **Ambiguous write retried blindly:** a non-idempotent `POST` is resent → a duplicate, or a conflict error that the caller takes for a new failure.
- **No timeout:** a black-holed connection is never answered or reset → the caller waits forever.
- **Asymmetric partition:** heartbeats flow one way → failure detectors disagree, and a dead or isolated node stays leader, or two leaders appear.
- **Split brain on failover:** both sides accept writes during the partition → divergent data that must be reconciled by hand (GitHub, 2018).
- **Partition read as death:** a watcher cut off from a healthy node declares it dead and acts, restarting or failing over, on a false signal.

## Review checklist
- [ ] **Can every remote write's outcome be determined after a lost reply?** · Applies when: the diff adds a call that creates or changes something remotely (`POST`, `gh pr create`, a payment, a message send). · Block if: on a timeout or connection error the code neither retries with an idempotency key nor looks the resource up by a natural key before reporting failure or retrying.
- [ ] **Does every remote call time out?** · Applies when: the diff adds a network call or a subprocess that does network I/O. · Block if: there is no connect and read timeout (or an overall deadline), so a black-holed peer hangs the caller.
- [ ] **Is the behaviour during a partition chosen?** · Applies when: the diff adds a dependency on another service for a request path. · Block if: it is unstated whether the path fails fast, degrades or queues while that service is unreachable.
- [ ] **Can a partition create two writers?** · Applies when: the diff adds failover, leader election or "take over if the other side looks dead" logic. · Block if: there is no quorum or fencing token preventing both sides from acting at once (038-distributed-locks.md).
- [ ] **Are partition-tolerance mechanisms justified?** · Applies when: the diff adds quorums, consensus or multi-site replication. · Block if: there is one stateful node, and timeouts plus idempotent writes cover its remote calls.

## In the factory
- Every `git` and `gh` call is bounded by `COMMAND_TIMEOUT = 300` s (`factory/intake/webhook_adapter.py:65`, `_run` `:313-321`), so a black-holed GitHub produces an error, not a hang. Right (011-timeouts.md).
- Pushes are safe after an ambiguous failure: re-pushing the same SHA is a no-op (014-idempotency.md).
- Gap (low): `gh pr create` (`:506`) is an ambiguous write handled as a plain failure.
  - If GitHub creates the PR and the reply is lost (a reset, a 300 s timeout), `_run` raises and the run ends as `error` with no `pr_url` recorded.
  - The PR stays open on GitHub, untracked by the factory, its checks running for nothing.
  - A retry would get "A pull request already exists". A lookup by branch (`gh pr list --head <branch> --json url`, or `gh pr view <branch>`) after the failure resolves it (proof A, B; see GAPS.md).
  - Generic retries are the Retries row; this row is about resolving the one non-idempotent write.
- Partitions elsewhere:
  - Cloudflare to the Mac: `cloudflared` reconnects on its own, and `/trigger` is unreachable meanwhile. The sender must retry, which meets the missing idempotency key (Idempotency row).
  - The sandbox to its egress proxy: the agent's calls fail and the round errors.
  - A watcher partitioned from the host would see `alive_at` go stale and could not tell that from death (057-liveness-readiness-probes.md).
- Not applicable at today's load: quorums, fencing and multi-site failover.

## Proof
`pytest -s knowledge/systems/proofs/095_partitions.py` (Python 3.11). A uses real sockets: client, then a proxy, then a small "GitHub" server. During the partition the proxy relays the request and drops the reply. B is the real adapter through `tests/test_adapter.py`'s fixture: the fake `gh pr create` runs, and then its answer is lost:
```
A  create PR during the partition: client saw ReadError; server has 1 PR(s)
A  naive retry: 422 A pull request already exists for factory/abc.
A  idempotent client, look up by branch after the unclear failure: https://github.example/pull/1
B  run cd3994bd: status 'error', pr_url recorded None; PRs that exist on GitHub: ['https://example.invalid/pull/1']
```

## Related
034-cap-theorem.md, 011-timeouts.md, 014-idempotency.md, 012-retries.md, 038-distributed-locks.md, 033-leader-election.md, 057-liveness-readiness-probes.md

## Sources
- "The Network is Reliable", Peter Bailis and Kyle Kingsbury (ACM Queue, 2014; author's copy): https://aphyr.com/posts/288-the-network-is-reliable
- "October 21 post-incident analysis", GitHub Blog: https://github.blog/news-insights/company-news/oct21-post-incident-analysis/
