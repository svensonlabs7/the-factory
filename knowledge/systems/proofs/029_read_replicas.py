"""Read replicas.
A. Monotonic reads: a counter is written to the primary every 50 ms; replica r1 lags 60 ms, r2 lags 400 ms. A client
   reads 40 times with round-robin routing, with sticky routing (one replica per session), and with a minimum-version
   token (a replica answers only if it has reached the version the client last saw, else the read goes to the primary).
B. The factory: _gate_results reads the PR head with one call and the checks with another. If the second read is
   served by a lagging replica, it returns the previous commit's finished checks for the new head. The real
   _gate_results via tests/test_adapter.py's fixture; `_run` plays a GitHub whose two endpoints lag differently.
   Then a single snapshot read (`gh pr view --json headRefOid,statusCheckRollup`) that returns head and checks together."""
import json
import time

from test_adapter import adapter  # noqa: F401  (fixture)


class Primary:
    def __init__(self):
        self.start = time.monotonic()

    def version(self, lag=0.0):  # the version a replica with this lag has applied
        return max(0, int((time.monotonic() - self.start - lag) / 0.05))


def test_monotonic_reads():
    lags = {"r1": 0.06, "r2": 0.40}
    for mode in ("round-robin", "sticky", "min-version token"):
        p, seen, went_back, primary_reads = Primary(), [], 0, 0
        time.sleep(0.5)
        token = 0
        for i in range(40):
            replica = ["r1", "r2"][i % 2] if mode != "sticky" else "r2"
            v = p.version(lags[replica])
            if mode == "min-version token" and v < token:
                v, primary_reads = p.version(), primary_reads + 1
            if seen and v < seen[-1]:
                went_back += 1
            seen.append(v)
            token = max(token, v)
            time.sleep(0.01)
        extra = f", {primary_reads} reads fell back to the primary" if mode.startswith("min") else ""
        print(f"{chr(10) if mode == 'round-robin' else ''}A  {mode:<18}: version went backwards {went_back:>2} times in 40 reads{extra}")


def test_gate_two_reads(adapter, monkeypatch):
    module, root, client = adapter
    checks = {"old111": [{"name": "tests", "bucket": "fail"}], "new222": [{"name": "tests", "bucket": "pass"}]}

    def fake_run(*cmd, cwd=None):
        if cmd[1:3] == ("pr", "view") and "headRefOid,statusCheckRollup" in cmd:
            return json.dumps({"headRefOid": "new222", "statusCheckRollup": [{"name": "tests", "conclusion": "SUCCESS"}]})
        if cmd[1:3] == ("pr", "view"):
            return "new222"                       # this replica has caught up with the push
        return json.dumps(checks["old111"])       # the checks are served by a replica that has not

    monkeypatch.setattr(module, "_run", fake_run)
    print(f"B  two reads (head, then checks): _gate_results('url', 'new222') -> {module._gate_results('url', 'new222')}")
    snap = json.loads(fake_run("gh", "pr", "view", "url", "--json", "headRefOid,statusCheckRollup"))
    verdict = {c["name"]: module._check_result(c) for c in snap["statusCheckRollup"]} if snap["headRefOid"] == "new222" else "not yet"
    print(f"B  one snapshot read (head and checks together): head {snap['headRefOid']} -> {verdict}")
