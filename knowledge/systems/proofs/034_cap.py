"""CAP: what a replicated register does during a partition.
A. Three replicas, partitioned {n1, n2} | {n3}. Each side receives writes during the partition, then the partition heals.
   CP (majority quorum): the minority side refuses; no divergence. AP (accept locally, last-write-wins on heal):
   every request is answered, but one side's writes are silently overwritten.
B. The factory makes this choice per operation. Real adapter (tests/test_adapter.py's fixture) with GitHub
   unreachable: the dashboard read answers with what it has (A), the gate refuses to guess (C)."""
import json
import time

from test_adapter import adapter  # noqa: F401  (fixture)


class Cluster:
    def __init__(self, mode):
        self.mode, self.nodes = mode, {n: {"value": None, "ts": 0.0} for n in ("n1", "n2", "n3")}
        self.side = {"n1": {"n1", "n2"}, "n2": {"n1", "n2"}, "n3": {"n3"}}  # who each node can reach

    def write(self, via, value):
        reach = self.side[via]
        if self.mode == "CP" and len(reach) < 2:              # no majority of 3 on this side
            return "rejected (no quorum)"
        for n in reach:
            self.nodes[n] = {"value": value, "ts": time.monotonic()}
        return "ok"

    def heal(self):
        if self.mode == "AP":                                 # last-write-wins across the old sides
            winner = max(self.nodes.values(), key=lambda s: s["ts"])
            for n in self.nodes:
                self.nodes[n] = dict(winner)
        else:                                                 # the minority catches up from the majority
            self.nodes["n3"] = dict(self.nodes["n1"])


def test_cp_vs_ap():
    for mode in ("CP", "AP"):
        c = Cluster(mode)
        majority = c.write("n1", "order A (majority side)")
        time.sleep(0.01)
        minority = c.write("n3", "order B (minority side)")
        c.heal()
        final = {s["value"] for s in c.nodes.values()}
        print(f"{chr(10) if mode == 'CP' else ''}A  {mode}: write via n1 -> {majority}; write via n3 -> {minority}; after heal every node holds {final}")


def test_factory_choices(adapter, monkeypatch):
    module, root, client = adapter
    (module.LOG_DIR / "r1.meta.json").write_text(json.dumps({"run_id": "r1", "status": "completed", "pr_url": "https://github.com/o/r/pull/9", "queued_at": 1}))

    def unreachable(*cmd, cwd=None):
        raise RuntimeError(f"{' '.join(cmd[:3])}: dial tcp api.github.com:443: no route to host")

    monkeypatch.setattr(module, "_run", unreachable)
    module._pr_cache.clear()
    r = client.get("/command/data")
    run = next(x for x in r.json()["runs"] if x["run_id"] == "r1")
    print(f"B  dashboard read while GitHub is unreachable: HTTP {r.status_code}, run {run['run_id']} status {run['status']!r}, pr {run['pr']}")
    try:
        module._gate_results("https://github.com/o/r/pull/9", "abc")
        gate = "returned a verdict"
    except RuntimeError as exc:
        gate = "raised RuntimeError: " + str(exc).split(": ", 1)[1]
    print(f"B  gate verdict while GitHub is unreachable: {gate}")
