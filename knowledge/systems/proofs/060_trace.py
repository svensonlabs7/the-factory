"""Reconstruct one factory run as a trace from existing records, joined by correlation keys:
run_id -> meta.json + actions.jsonl -> pushed head sha -> GitHub Actions runs and jobs for that sha (read-only API).
Prints spans on a common clock (seconds from trigger) to show where the time went."""
import datetime as dt
import json
import subprocess
import sys

logs, run_id, repo = sys.argv[1], sys.argv[2], "svensonlabs7/the-factory"
meta = json.load(open(f"{logs}/{run_id}.meta.json"))
events = [json.loads(l) for l in open(f"{logs}/{run_id}.actions.jsonl")]
t0 = meta["queued_at"]
iso = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
spans = []  # (start, end, depth, name)

spans.append((t0, meta["finished_at"], 0, f"run {run_id} ({meta['status']})"))
starts = {e["attempt"]: e["time"] for e in events if e["event"] == "round_started"}
for e in events:
    if e["event"] == "round_finished":
        spans.append((starts[e["attempt"]], e["time"], 1, f"build round {e['attempt']} (sandbox agent, exit {e.get('exit_code')})"))
head = next(e["head"] for e in events if e["event"] == "pushed")
pushed = next(e["time"] for e in events if e["event"] == "pushed")
opened = next(e["time"] for e in events if e["event"] == "pr_opened")
gate = next(e["time"] for e in events if e["event"] == "gate_result")
spans.append((pushed, opened, 1, "gh pr create"))
spans.append((opened, gate, 1, "adapter waits for required checks"))

runs = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/actions/runs?head_sha={head}", "--jq", ".workflow_runs"],
                                 capture_output=True, text=True).stdout)
for r in runs:
    jobs = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/actions/runs/{r['id']}/jobs", "--jq", ".jobs"],
                                     capture_output=True, text=True).stdout)
    for j in jobs:
        if j.get("started_at") and j.get("completed_at"):
            spans.append((iso(j["started_at"]), iso(j["completed_at"]), 2, f"CI {r['name']} / {j['name']} ({j['conclusion']})"))

print(f"trace for run {run_id}: join keys run_id={run_id}, head sha={head[:12]}, {len(runs)} workflow runs found by sha\n")
for start, end, depth, name in sorted(spans):
    print(f"{start - t0:8.0f}s {end - t0:8.0f}s {end - start:7.0f}s  {'  ' * depth}{name}")
total = meta["finished_at"] - t0
build = sum(e - s for s, e, d, n in spans if n.startswith("build round"))
print(f"\nwhere the {total:.0f} s went: building {build:.0f} s ({build / total:.0%}), waiting for the gate {gate - opened:.0f} s ({(gate - opened) / total:.0%})")
