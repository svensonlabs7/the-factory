"""Error budget for the factory's own SLO, from its real runs.
SLO (from 063-slos.md, starter): 80% of triggered runs are delivered autonomously, meaning status 'completed'
and PR merged. Budget = 20% of runs. Each miss is attributed to a cause, and the policy rule from the SRE workbook
is applied: any single cause using more than 20% of the budget gets a P0 item."""
import collections
import glob
import json
import re
import subprocess
import sys

logs, target = sys.argv[1], 0.80
runs = sorted((json.load(open(p)) for p in glob.glob(f"{logs}/*.meta.json")), key=lambda r: r["queued_at"])
misses = []
for r in runs:
    state = json.loads(subprocess.run(["gh", "pr", "view", r["pr_url"], "--json", "state"], capture_output=True, text=True).stdout)["state"] if r.get("pr_url") else "none"
    if r["status"] == "completed" and state == "MERGED":
        continue
    raw = open(f"{logs}/{r['run_id']}.log", errors="ignore").read()
    if r["status"] == "failed" and re.search(r"ConversationRunError.*session limit", raw, re.S):
        cause = "plan usage limit"
    elif r["status"] == "blocked":
        cause = "gate kept blocking (fix rounds did not converge)"
    elif r["status"] == "completed":
        cause = "gate passed a change that did not work (closed)"
    else:
        cause = f"other: {r['status']}"
    misses.append((r["run_id"], cause))

budget = len(runs) * (1 - target)
print(f"runs {len(runs)}, SLO {target:.0%} -> error budget {budget:.1f} misses; used {len(misses)} = {len(misses) / budget:.0%} of budget")
for cause, n in collections.Counter(c for _, c in misses).items():
    share = n / budget
    print(f"  {cause:<50} {n} miss = {share:.0%} of budget {'-> P0 item (over 20%)' if share > 0.20 else ''}")
print("policy:", "budget exceeded -> freeze factory feature work; reliability fixes only" if len(misses) > budget else "within budget")
print(f"same runs under a 99% SLO: budget {len(runs) * 0.01:.2f} misses -> one miss is {1 / (len(runs) * 0.01):.0%} of budget")
