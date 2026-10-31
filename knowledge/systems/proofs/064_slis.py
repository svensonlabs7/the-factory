"""Two SLIs for the same factory runs, measured at different points.
Server-side (easy): good = run ended 'completed' (the gate passed).
Closer to the user: good = the run's PR was merged (the feature actually shipped). Plus a latency SLI: queue -> merge.
Reads .factory-logs/*.meta.json and asks GitHub (read-only) for each PR's state."""
import glob
import json
import subprocess
import sys

runs = sorted((json.load(open(p)) for p in glob.glob(f"{sys.argv[1]}/*.meta.json")), key=lambda r: r["queued_at"])
rows = []
for r in runs:
    pr = {}
    if r.get("pr_url"):
        pr = json.loads(subprocess.run(["gh", "pr", "view", r["pr_url"], "--json", "state,mergedAt,number"],
                                       capture_output=True, text=True).stdout or "{}")
    rows.append((r["run_id"], r["status"], pr.get("number"), pr.get("state", "no PR")))
    print(f"  {r['run_id']}  status={r['status']:<9} PR #{pr.get('number', '-'):<3} {pr.get('state', 'no PR')}")

n = len(rows)
completed = sum(s == "completed" for _, s, _, _ in rows)
merged = sum(st == "MERGED" for _, _, _, st in rows)
both = [(rid, num) for rid, s, num, st in rows if s == "completed" and st != "MERGED"]
bad_but_merged = [(rid, num) for rid, s, num, st in rows if s != "completed" and st == "MERGED"]
print(f"SLI server-side  'run completed':  {completed}/{n} = {completed / n:.0%}")
print(f"SLI user-facing  'PR merged':      {merged}/{n} = {merged / n:.0%}")
print(f"  counted good by the server, not shipped: {both}")
print(f"  counted bad by the server, shipped anyway (a human finished it): {bad_but_merged}")
