"""Cost optimization: attribute the factory's binding cost, Claude sessions, to output, from the real GitHub record
(read-only gh calls). GitHub Actions minutes cost nothing here (public repo, standard runners).
A. Gate runs, PRs and outcomes: Claude review sessions per merged PR.
B. What the ux-laws path scoping saves: lanes that skipped the Claude call, over the last 30 gate runs.
C. Spend that produced no merge: review sessions on PRs that were closed."""
import json
import subprocess


def gh(*args):
    return json.loads(subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout)


runs = gh("run", "list", "--workflow", "qa-gate.yml", "--limit", "1000", "--json", "databaseId,event,headBranch")
prs = gh("pr", "list", "--state", "all", "--limit", "200", "--json", "number,state,headRefName")
merged = [p for p in prs if p["state"] == "MERGED"]
closed = [p for p in prs if p["state"] == "CLOSED"]

recent, ran = runs[:30], {"thermo-nuclear": 0, "ponytail-review": 0, "ux-laws": 0}
for r in recent:
    for job in gh("run", "view", str(r["databaseId"]), "--json", "jobs")["jobs"]:
        review = next((s for s in job["steps"] if s["name"] == "Review"), None)
        if review and review["conclusion"] in ("success", "failure"):
            ran[job["name"]] += 1
per_run = sum(ran.values()) / len(recent)
total_sessions = per_run * len(runs)
print(f"A  {len(runs)} gate runs for {len(prs)} PRs ({len(runs) / len(prs):.2f} runs per PR); {len(merged)} merged, {len(closed)} closed")
print(f"A  Claude review sessions per gate run {per_run:.2f} -> about {total_sessions:.0f} sessions, {total_sessions / len(merged):.1f} per merged PR")
print(f"B  last 30 gate runs: Claude review ran thermo-nuclear {ran['thermo-nuclear']}, ponytail-review {ran['ponytail-review']}, ux-laws {ran['ux-laws']} of 30")
print(f"B  ux-laws path scoping avoided {30 - ran['ux-laws']} of {30 * 3} possible review sessions ({(30 - ran['ux-laws']) / 90:.0%})")
closed_branches = {p["headRefName"] for p in closed}
wasted = sum(1 for r in runs if r["headBranch"] in closed_branches)
print(f"C  gate runs on PRs that were then closed: {wasted} of {len(runs)} ({wasted / len(runs):.0%}), about {wasted * per_run:.0f} review sessions with no merge")
