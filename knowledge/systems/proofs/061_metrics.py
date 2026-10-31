"""The four golden signals for the factory, computed from what it already records: .factory-logs/*.meta.json
(one per run) and *.actions.jsonl (events, only for runs since the action log shipped)."""
import collections
import glob
import json
import re
import statistics
import sys
import time

logs = sys.argv[1]
runs = [json.load(open(p)) for p in glob.glob(f"{logs}/*.meta.json")]
actions = {p.split("/")[-1].split(".")[0]: [json.loads(l) for l in open(p)] for p in glob.glob(f"{logs}/*.actions.jsonl")}
day = lambda t: time.strftime("%Y-%m-%d", time.gmtime(t))

print(f"runs on disk: {len(runs)} (with an action log: {len(actions)})")
print("TRAFFIC   runs queued per day:", dict(sorted(collections.Counter(day(r["queued_at"]) for r in runs if r.get("queued_at")).items())))
outcomes = collections.Counter(r.get("status") for r in runs)
print(f"ERRORS    outcomes: {dict(outcomes)}; success rate {outcomes['completed'] / len(runs):.0%}")
print(f"          completed on the first build (attempt 0): {sum(r.get('status') == 'completed' and r.get('attempt') == 0 for r in runs)}/{outcomes['completed']}")
durations = sorted((r["finished_at"] - r["started_at"]) / 60 for r in runs if r.get("finished_at") and r.get("started_at"))
waits = sorted((r["started_at"] - r["queued_at"]) / 60 for r in runs if r.get("started_at") and r.get("queued_at"))
print(f"LATENCY   run minutes: median {statistics.median(durations):.1f}, max {max(durations):.1f}; queue wait minutes: median {statistics.median(waits):.1f}, max {max(waits):.1f}")
rounds = [e["seconds"] for evs in actions.values() for e in evs if e["event"] == "round_finished" and "seconds" in e]
print(f"          build-round seconds (action log): {sorted(round(s) for s in rounds)}")
spans = sorted((r["queued_at"], r.get("finished_at", r["queued_at"])) for r in runs if r.get("queued_at"))
peak = max(sum(q <= t < f for q, f in spans) for t, _ in spans)
print(f"SATURATION peak runs in flight: {peak} of MAX_PENDING 5; busiest day: {max(collections.Counter(day(q) for q, _ in spans).values())} of MAX_RUNS_PER_DAY 30")
pause_events = sum(e["event"].startswith("pause") for evs in actions.values() for e in evs)
limit_hits = sum(bool(re.search(r"session limit|usage limit", open(p, errors="ignore").read(), re.I)) for p in glob.glob(f"{logs}/*.log") if "intake" not in p)
print(f"          plan usage-limit hits: action-log events {pause_events}; found only by grepping raw run logs: {limit_hits} run(s)")
