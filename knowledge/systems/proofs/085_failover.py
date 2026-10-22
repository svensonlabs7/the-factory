"""Failover: when the primary fails, promote a standby to take over. The hard part is telling 'the primary is
DEAD' from 'I just can't REACH the primary' (a network partition, 095). A standby that promotes on unreachability
alone creates SPLIT-BRAIN: the old primary is still alive and serving, now there are two primaries, and they
accept conflicting writes that diverge. Fencing/quorum (a lease the old primary must hold, STONITH, majority
vote) prevents it: a standby may promote only once it can be sure the old primary can no longer act.

Model a primary P holding a lease, a standby S, and two failure scenarios: a partition (P alive but unreachable
by S) and a true crash (P dead, lease expires). Compare naive failover (promote on unreachable) vs fenced
(promote only if P's lease has expired). Count primaries and whether writes diverged. Deterministic; no network."""


def run(scenario, fenced):
    # P holds a lease; lease_valid = P is alive and still within its lease.
    p_alive = scenario != "crash"
    s_can_reach_p = scenario == "healthy"
    lease_held_by_p = p_alive            # a live P keeps renewing its lease; a dead P lets it expire

    primaries = {"P"} if p_alive else set()
    if not s_can_reach_p:                # S's health check of P fails (partition OR crash look identical to S)
        if fenced:
            if not lease_held_by_p:      # fenced: promote only once P's lease is gone (P provably cannot act)
                primaries.add("S")
        else:
            primaries.add("S")           # naive: promote on unreachability alone

    diverged = len(primaries) > 1 and p_alive   # two primaries both accepting writes
    return primaries, diverged


for fenced in (False, True):
    print(f"{'fenced (lease/quorum)' if fenced else 'naive (promote on unreachable)'}:")
    for scenario in ("healthy", "partition", "crash"):
        primaries, diverged = run(scenario, fenced)
        note = "SPLIT-BRAIN, writes diverge" if diverged else ("failed over cleanly" if primaries == {"S"}
               else "no failover needed" if primaries == {"P"} else "down (no primary)")
        plist = ",".join(sorted(primaries)) or "-"
        print(f"   {scenario:9s}: primaries={plist:5} -> {note}")
    print()
