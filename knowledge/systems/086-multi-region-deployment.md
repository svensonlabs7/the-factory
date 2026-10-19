# 86. Multi-Region Deployment

Track: L. Operations · Status: proven · Updated: 2026-10-19

## What it is
A multi-region deployment runs the system in two or more geographic regions, for **latency** (serve each user from a nearby region) and **survival** (a whole region — not just a host — can fail and the service continues). The shapes mirror failover (085) at continental scale: **active-passive** (one region serves, another stands by and is promoted on regional failure) and **active-active** (all regions serve traffic at once). The unavoidable physics is the speed of light: a cross-region round trip is tens of milliseconds, so **synchronous** replication across regions is too slow for most writes, and you replicate **asynchronously**. Async replication means the other region lags, and that lag has two hard consequences (proof): on an active-passive failover, every write not yet replicated is lost — the data loss (RPO) equals the lag; and in active-active, two regions can accept conflicting writes to the same key, which an async last-write-wins merge silently resolves by dropping one, unless you add real conflict resolution (CRDTs, vector clocks — 035-eventual-consistency.md). Multi-region is CAP (034) made geographic: a partition between regions forces the choice between consistency and availability.

## When it is worth it
- Worth it for systems with a **global user base** that needs low latency everywhere, or a **survival requirement** that a single region's loss must not cause an outage or data loss beyond a tight RPO/RTO. That is a real need for large consumer services, payment systems, and anything with a regional-resilience SLA.
- It is one of the most over-engineered things in practice. It multiplies cost and, more importantly, forces every stateful component to confront cross-region consistency — conflict resolution, data residency, failover testing, replication monitoring. For a system whose users are in one region and that tolerates a rebuild (083) or a short outage, multi-region adds enormous complexity for resilience nobody needs. Most systems should exhaust single-region multi-AZ redundancy first.

## How it fails
- **Data loss on regional failover:** async replication lag means recent writes are not in the surviving region when the primary region is lost (proof: RPO = lag).
- **Active-active write conflicts:** concurrent writes to the same key in two regions diverge; last-write-wins drops data silently (proof), and ad-hoc resolution corrupts state (035-eventual-consistency.md).
- **Split-brain across regions:** a partition between regions, with both continuing to accept writes, is failover's split-brain at scale (085-failover.md, 095-network-partitions.md).
- **Untested regional failover:** the standby region drifts or its promotion path is broken, discovered only in a real regional outage (083-disaster-recovery.md).
- **Hidden single-region dependency:** a "multi-region" system still routes through one region's database, queue, or auth, so that region's loss takes everything down anyway.
- **Data-residency / cost surprises:** replicating data to another region violates a residency rule, or the cross-region traffic and duplicate capacity cost far more than expected.

## Review checklist
- [ ] **Is the failover data-loss window (RPO) stated and acceptable?** · Applies when: the diff adds or relies on cross-region replication with regional failover. · Block if: replication is async and the resulting RPO (lag at failure) is not stated or exceeds what the data can tolerate.
- [ ] **Does active-active have real conflict resolution?** · Applies when: the diff lets more than one region accept writes to the same data. · Block if: concurrent cross-region writes are merged by bare last-write-wins where silent data loss is unacceptable, with no CRDT/version-based resolution.
- [ ] **Is there a hidden single-region dependency?** · Applies when: the diff adds a component to a multi-region system. · Block if: a supposedly regional path still depends on one region's database, queue or auth, defeating the survival goal.
- [ ] **Is multi-region justified over single-region redundancy?** · Applies when: the diff introduces a second region. · Block if: users are regional and the system tolerates a rebuild or short outage, where multi-AZ redundancy in one region would meet the need without cross-region consistency cost.

## In the factory
- **Single region, and multi-region would be extreme over-engineering.** The factory is one Mac in one place, one operator, no external users with a latency or regional-resilience need. Running a second region — and taking on cross-region replication, conflict resolution and failover testing for a webhook and a dashboard — would be the textbook case this card warns against.
- **The edge is already multi-location; the origin is deliberately not.** Cloudflare serves the two hostnames from its global anycast network (responses seen from the `EWR` POP — 097-dns.md, 048-cdn.md), so clients get a nearby edge regardless. But that is edge routing, not a multi-region origin: behind the tunnel there is exactly one origin host (003-load-balancing.md). This is the right split — global edge, single origin — for one operator.
- **The survival need the factory actually has is disaster recovery, not multi-region:** rebuild the one host from backups and a runbook (083-disaster-recovery.md, 084-backups.md), accepting hours of downtime. That is the proportionate tier; a hot second region is not.
- Not applicable at today's load: cross-region replication, active-active, GeoDNS failover, data-residency controls, regional capacity.

## Proof
`python3 086_multi_region.py`, modelling async cross-region replication:
```
A  active-passive, async lag= 0 ticks:  0 writes lost on failover (RPO = the lag)
A  active-passive, async lag= 3 ticks:  3 writes lost on failover (RPO = the lag)
A  active-passive, async lag=10 ticks: 10 writes lost on failover (RPO = the lag)
B  active-active (last-write-wins): state={'x': 'set-from-B'}  dropped=['set-from-A']
B  active-active (crdt           ): state={'x': {'A': 'set-from-A', 'B': 'set-from-B'}}  dropped=none
```
A: on a regional failover the surviving region is missing exactly the writes still in flight — the data loss equals the async replication lag, so cross-region async replication always has a non-zero RPO. B: when both regions write the same key, a last-write-wins merge silently drops one region's write; only real conflict resolution (a CRDT/vector clock) keeps both. Cross-region latency forces the async choice, and the async choice forces these trade-offs.

## Related
083-disaster-recovery.md, 085-failover.md, 032-replication.md, 034-cap-theorem.md, 035-eventual-consistency.md, 095-network-partitions.md, 048-cdn.md

## Sources
- "Multi-Region fundamentals" and failover/replication trade-offs, AWS: https://docs.aws.amazon.com/whitepapers/latest/aws-multi-region-fundamentals/aws-multi-region-fundamentals.html
- "Data consistency across regions" (async replication, RPO), AWS Well-Architected Reliability pillar: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/plan-for-disaster-recovery-dr.html
