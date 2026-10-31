"""N+1 queries.
A. SQLite: 100 runs and their events, loaded three ways. Statements are counted with set_trace_callback, and each
   statement pays a 1 ms round trip, as a networked database would.
B. The factory: /command/data makes one `gh pr view` per PR (the real _pr and command_data, through
   tests/test_adapter.py's fixture; `_run` is replaced to count calls and cost 50 ms each, a tenth of the real 0.48 s)."""
import json
import random
import sqlite3
import time

from test_adapter import adapter  # noqa: F401  (fixture)


def test_orm_shapes():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE runs(id INTEGER PRIMARY KEY, queued_at REAL)")
    db.execute("CREATE TABLE events(run_id INTEGER, name TEXT)")
    db.execute("CREATE INDEX events_run ON events(run_id)")
    rng = random.Random(1)
    db.executemany("INSERT INTO runs VALUES (?,?)", ((i, i) for i in range(10_000)))
    db.executemany("INSERT INTO events VALUES (?,?)", ((rng.randrange(10_000), "e") for _ in range(50_000)))
    count = [0]

    def trace(_sql):
        count[0] += 1
        time.sleep(0.001)  # network round trip

    db.set_trace_callback(trace)

    def lazy():
        runs = db.execute("SELECT id FROM runs ORDER BY queued_at DESC LIMIT 100").fetchall()
        return {r: db.execute("SELECT name FROM events WHERE run_id = ?", (r,)).fetchall() for (r,) in runs}

    def batched():
        runs = [r for (r,) in db.execute("SELECT id FROM runs ORDER BY queued_at DESC LIMIT 100")]
        out = {r: [] for r in runs}
        for run_id, name in db.execute(f"SELECT run_id, name FROM events WHERE run_id IN ({','.join('?' * len(runs))})", runs):
            out[run_id].append((name,))
        return out

    def joined():
        out = {}
        for run_id, name in db.execute("SELECT r.id, e.name FROM (SELECT id FROM runs ORDER BY queued_at DESC LIMIT 100) r LEFT JOIN events e ON e.run_id = r.id"):
            out.setdefault(run_id, []).append((name,)) if name else out.setdefault(run_id, [])
        return out

    results = {}
    for label, fn in (("lazy loop (N+1)", lazy), ("IN batch (selectin)", batched), ("one JOIN", joined)):
        count[0] = 0
        t = time.perf_counter()
        results[label] = fn()
        ms = (time.perf_counter() - t) * 1e3
        events = sum(len(v) for v in results[label].values())
        print(f"{'' if label.startswith('lazy') else ''}A  {label:<20}: {count[0]:>3} statements, {ms:6.1f} ms, {len(results[label])} runs / {events} events")


def test_dashboard_gh_calls(adapter, monkeypatch):
    module, root, client = adapter
    calls, states = [], {}

    def fake_run(*cmd, cwd=None):
        if cmd[1:3] == ("pr", "view"):
            calls.append(cmd[3])
            time.sleep(0.05)
            return json.dumps({"state": states[cmd[3]], "statusCheckRollup": [{"name": "tests", "conclusion": "SUCCESS"}]})
        raise RuntimeError("unexpected")

    monkeypatch.setattr(module, "_run", fake_run)
    for n in (12, 60, 300):
        module._pr_cache.clear()
        for p in module.LOG_DIR.glob("n*.meta.json"):
            p.unlink()
        for i in range(n):
            url = f"https://github.com/o/r/pull/{i}"
            states[url] = "MERGED"
            (module.LOG_DIR / f"n{i:04d}.meta.json").write_text(json.dumps({"run_id": f"n{i:04d}", "status": "completed", "pr_url": url, "queued_at": i}))
        row = []
        for label in ("cold cache", "warm, merged"):
            calls.clear()
            t = time.perf_counter()
            assert client.get("/command/data").status_code == 200
            row.append(f"{label}: {len(calls):>3} gh calls {time.perf_counter() - t:5.2f} s")
        for url in states:
            states[url] = "OPEN"
        module._pr_cache.clear()
        client.get("/command/data")
        monkeypatch.setattr(module, "PR_CACHE_TTL", 0)  # past the 60 s TTL
        calls.clear()
        t = time.perf_counter()
        client.get("/command/data")
        row.append(f"all open, TTL passed: {len(calls):>3} gh calls {time.perf_counter() - t:5.2f} s")
        monkeypatch.setattr(module, "PR_CACHE_TTL", 60)
        print(f"B  {n:>3} PRs | " + " | ".join(row))
