"""Multi-region deployment runs the system in two or more geographic regions for latency (serve users nearby)
and survival (a whole region can fail). The physics is unavoidable: cross-region round trips are tens of ms, so
SYNCHRONOUS replication across regions is too slow for most writes -> you replicate ASYNC, and async means the
standby lags. Two consequences fall out:

A. active-passive: on a regional failover, every write that was made in the primary but not yet replicated is
   LOST. The data loss (RPO) equals the replication lag at the moment of failure.
B. active-active: both regions accept writes to the SAME key concurrently. Async last-write-wins merge keeps one
   and silently drops the other -> divergence, unless you add conflict resolution (CRDTs / vector clocks, 035).
Deterministic; no network."""

# A. active-passive: writes to the primary, replicated to the standby with a lag.
def failover_loss(total_writes, lag, fail_at):
    primary = list(range(total_writes))             # write ids applied at the primary, one per tick
    replicated = [w for w in primary if w < fail_at - lag]   # standby has only writes older than the lag
    if fail_at <= total_writes:
        lost = [w for w in primary if w < fail_at and w not in replicated]
        return len(lost)
    return 0


for lag in (0, 3, 10):
    lost = failover_loss(total_writes=100, lag=lag, fail_at=50)
    print(f"A  active-passive, async lag={lag:2d} ticks: {lost:2d} writes lost on failover (RPO = the lag)")

# B. active-active: regions A and B each accept a write to key 'x' in the same window; async merge.
def active_active(resolution):
    writes = [("A", "x", "set-from-A", 5), ("B", "x", "set-from-B", 5)]   # same key, same tick, two regions
    if resolution == "last-write-wins":
        winner = writes[-1]                          # a tie broken arbitrarily; the other is dropped
        return {winner[1]: winner[2]}, [w for w in writes if w is not winner]
    else:  # crdt / vector clock: keep both, flagged as a conflict to resolve
        return {"x": {"A": "set-from-A", "B": "set-from-B"}}, []


for resolution in ("last-write-wins", "crdt"):
    state, dropped = active_active(resolution)
    print(f"B  active-active ({resolution:15s}): state={state}  dropped={[w[2] for w in dropped] or 'none'}")
