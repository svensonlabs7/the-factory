# 85. Failover

Track: L. Operations · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)failover|\bpromot(e|ion)\b|\bstandby\b|virtual.?ip` · tripwire

## What it is
Failover is the automatic switch from a failed primary to a redundant standby so service continues with minimal interruption. A health check watches the primary; when it fails, a standby is **promoted** to take over, usually with traffic redirected by DNS, a load balancer, or a virtual IP (003-load-balancing.md, 097-dns.md). Failover handles the loss of a *component* while the rest of the environment stands — distinct from disaster recovery, which rebuilds a whole lost environment (083-disaster-recovery.md). The defining difficulty is that a health check cannot tell "the primary is **dead**" from "I can't **reach** the primary" (a network partition — 095-network-partitions.md). Promoting a standby on unreachability alone, when the old primary is actually alive, produces **split-brain**: two primaries accept conflicting writes that diverge (proof). The guard is **fencing** — a lease the old primary must hold, STONITH ("shoot the other node in the head"), or a quorum/witness — so a standby may promote only once the old primary provably can no longer act (033-leader-election.md).

## When it is worth it
- Worth it when a component's failure would cause unacceptable downtime and you have (or can afford) a standby to switch to: a replicated database with a promotable replica (032-replication.md), redundant load balancers, multi-AZ services. The investment is the standby plus the promotion machinery plus the fencing to make it safe.
- Over-engineering when there is nothing to fail over to, or the downtime of simply restarting in place is acceptable. A single instance with no standby cannot fail over; adding a second node *and* a consensus/fencing mechanism to a system that tolerates a quick restart buys little and adds split-brain risk that did not exist before. Recovery-in-place (restart, re-provision) is the right answer below that bar; failover is for when a restart is too slow or the box is gone.

## How it fails
- **Split-brain on a partition:** the standby promotes because it cannot reach a primary that is actually alive, so two primaries diverge (proof: naive failover split-brains on a partition; fencing does not).
- **No fencing / weak quorum:** promotion has no mechanism to guarantee the old primary stepped down, so even a brief blip can double-promote.
- **Flapping:** an over-sensitive health check fails over and back repeatedly on transient blips, each switch disrupting service (057-liveness-readiness-probes.md: tune thresholds).
- **Stale or lagging standby:** the standby is promoted but was behind on replication, losing recent writes (RPO miss — 032-replication.md, 084-backups.md).
- **Failover never drilled:** the standby or the promotion path is broken and nobody knows until the real failure (083: untested recovery has unknown behaviour).
- **Clients don't follow the switch:** DNS TTLs or cached connections keep sending traffic to the dead primary after promotion (097-dns.md: lower TTL before a planned switch).

## Review checklist
- [ ] **Is promotion fenced against split-brain?** · Applies when: the diff adds or changes automatic failover/promotion of a stateful primary. · Block if: a standby can promote on unreachability alone, with no lease, quorum or fencing guaranteeing the old primary has stepped down.
- [ ] **Is the health check tuned against flapping?** · Applies when: the diff sets the failure detection that triggers failover. · Block if: a single transient failure triggers promotion, or there is no hysteresis/cooldown, so the system can flap.
- [ ] **Is the standby fresh enough to meet RPO on promotion?** · Applies when: the diff relies on promoting a replica. · Block if: replication lag can exceed the acceptable data loss and promotion proceeds anyway.
- [ ] **Is failover justified over recovery-in-place?** · Applies when: the diff introduces a standby and promotion machinery. · Block if: there is no standby to switch to, or a restart/re-provision meets the downtime budget — adding a second node plus fencing where a restart would do is complexity (and new split-brain risk) for little gain.

## In the factory
- **There is no failover, and that is correct: one instance, recovery in place.** The adapter is a single process; launchd `KeepAlive` restarts it if it dies (`com.svenson.factory-intake.plist:38`, 008-kubernetes.md). That is recovery-in-place, not failover — same machine, same identity, and crucially **there is never a second instance**, so split-brain is structurally impossible. For a one-operator tool whose restart is seconds, this is the right tier; a hot standby with fencing would add the exact split-brain risk this card warns about, for no gain.
- **The factory already enforces the single-writer invariant that failover's fencing exists to protect:** one `ThreadPoolExecutor(max_workers=1)`, a capacity check with no `await` before the write, and a file-per-signature replay store that survives restart (`webhook_adapter.py:151,227-231`, 039-race-conditions.md). Only one actor ever mutates run state.
- **A prior review already caught the fencing lesson in a factory-shaped form:** cards 037/038 corrected the claim that binding `127.0.0.1:7654` is a single-instance lock — a bound port is not a lease, so two adapters started at once would both run `_recover` before either failed to bind (REVIEWS.md, 50-card review). That is the "a port is not fencing" point this topic generalises.
- Not applicable at today's load: standby promotion, virtual IPs, DNS/LB failover, STONITH, quorum witnesses, replica promotion.

## Proof
`python3 knowledge/systems/proofs/085_failover.py`, a primary P holding a lease and a standby S, under three scenarios, with naive vs fenced promotion:
```
naive (promote on unreachable):
   healthy  : primaries=P     -> no failover needed
   partition: primaries=P,S   -> SPLIT-BRAIN, writes diverge
   crash    : primaries=S     -> failed over cleanly

fenced (lease/quorum):
   healthy  : primaries=P     -> no failover needed
   partition: primaries=P     -> no failover needed
   crash    : primaries=S     -> failed over cleanly
```
Naive failover cannot distinguish a partition from a crash, so on a partition it promotes S while P is still alive — two primaries, diverging writes. Fenced failover promotes only once P's lease has expired, so a partition (P still holding its lease) causes no promotion, and a true crash (lease expired) fails over cleanly. Fencing is what makes failover safe.

## Related
083-disaster-recovery.md, 032-replication.md, 033-leader-election.md, 095-network-partitions.md, 057-liveness-readiness-probes.md, 003-load-balancing.md, 086-multi-region-deployment.md

## Sources
- "Fencing" and split-brain prevention, Linux-HA / Pacemaker documentation: https://clusterlabs.org/pacemaker/doc/
- "Reliability pillar — Failover and health checks", AWS Well-Architected: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/use-fault-isolation-to-protect-your-workload.html
