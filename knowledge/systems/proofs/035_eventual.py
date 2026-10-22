"""Eventual consistency.
A. Quorums over N=3 replicas with random propagation delay (0-100 ms): probability a read 10 ms after a write sees it,
   for W=1/R=1 vs W=2/R=2 (W+R>N). 10,000 trials, seeded.
B. Convergence is not correctness: two replicas each take 5 increments while partitioned. Last-write-wins converges
   on 5; a grow-only counter (a CRDT: per-replica counts, merged by max) converges on 10.
C. The factory: the dashboard's PR cache (real _pr via tests/test_adapter.py's fixture) treats CLOSED as final, but a
   closed PR can be reopened. After a reopen, and past the 60 s TTL, the dashboard still says CLOSED."""
import json
import random
import time

from test_adapter import adapter  # noqa: F401  (fixture)


def test_quorum_staleness():
    rng = random.Random(4)
    for w, r in ((1, 1), (2, 2)):
        fresh = 0
        for _ in range(10_000):
            arrival = sorted(rng.uniform(0, 0.1) for _ in range(3))
            arrival[:w] = [0.0] * w                    # the write returns once W replicas have it
            read_at = 0.01
            asked = rng.sample(range(3), r)
            fresh += any(arrival[i] <= read_at for i in asked)
        print(f"{chr(10) if w == 1 else ''}A  W={w} R={r} (W+R{'>' if w + r > 3 else '<='}3): read 10 ms after the write sees it {fresh / 100:.1f}% of the time")


def test_convergence():
    a, b = {"value": 0, "ts": 0.0}, {"value": 0, "ts": 0.0}
    for i in range(5):
        a = {"value": a["value"] + 1, "ts": time.monotonic()}
        b = {"value": b["value"] + 1, "ts": time.monotonic()}
    lww = max(a, b, key=lambda s: s["ts"])["value"]
    ga, gb = {"A": 5, "B": 0}, {"A": 0, "B": 5}             # each replica counts its own increments
    merged = {k: max(ga[k], gb[k]) for k in ga}
    print(f"B  10 increments across a partition: last-write-wins converges on {lww}; grow-only counter converges on {sum(merged.values())}")


def test_dashboard_cache(adapter, monkeypatch):
    module, root, client = adapter
    url, state = "https://github.com/o/r/pull/7", {"s": "CLOSED"}
    monkeypatch.setattr(module, "_run", lambda *cmd, cwd=None: json.dumps({"state": state["s"], "statusCheckRollup": []}))
    module._pr_cache.clear()
    first = module._pr(url)["state"]
    state["s"] = "OPEN"                                         # someone reopens the PR
    monkeypatch.setattr(module, "PR_CACHE_TTL", 0)              # well past the 60 s TTL
    later = module._pr(url)["state"]
    state["s"], module._pr_cache = "MERGED", {}
    print(f"C  PR seen {first}, then reopened on GitHub: dashboard after the TTL says {later!r}")
