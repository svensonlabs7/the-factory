#!/usr/bin/env python3
"""Where the factory spends rework, and one proposal to cut the worst of it. From the QA gate's results on recent PRs
it counts the pushes each check failed, and from .factory-logs how factory runs ended. The check that failed the most
pushes is the top problem, and its latest block reasons go into a proposed task. Read-only, except that --file opens
the proposal as an issue labeled kaizen for the operator to approve. It opens none while one is open, so one
improvement is in flight at a time. Usage: factory/qa/kaizen_report.py [--prs 40] [--file]"""
import argparse
import collections
import json
import pathlib
import statistics
import tempfile

from router_report import gh

LOG_DIR = pathlib.Path(__file__).resolve().parents[2] / ".factory-logs"
FAILED = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE"}  # CANCELLED is a push a newer one replaced, not a failure
REVIEWED = {"thermo-nuclear", "ponytail-review", "ux-laws"}  # the lanes that upload review-<check> (qa-gate.yml)
REVIEW_NOT_RUN = "REVIEW-NOT-RUN"  # what qa-gate.yml writes when the reviewer crashed: not a finding
EVIDENCE = 6  # the latest block reasons quoted in a proposal
REASON_LIMIT = 600
LABEL = "kaizen"
QUERY = """query($owner: String!, $name: String!, $n: Int!) { repository(owner: $owner, name: $name) {
  pullRequests(last: $n, orderBy: {field: CREATED_AT, direction: ASC}) { nodes { number headRefName merged
    commits(first: 100) { nodes { commit { statusCheckRollup { contexts(first: 30) { nodes {
      ... on CheckRun { name conclusion checkSuite { workflowRun { databaseId } } } } } } } } } } } } }"""
TASK = """Cut the rework the {check} check causes. Across the last {prs} PRs it failed {count} pushes, more than any \
other check, and each failed push is another round of fixes. Its latest block reasons are below. Group them by root \
cause, pick the largest group, and add the cheapest check that catches that kind of problem before the gate runs: a \
rule in factory/qa/rules.py, a test, or an instruction the builder gets. Do not loosen the gate or edit its review \
skills. In the PR, name the group, the reviews it covers, and why your check catches it.

Block reasons:
{evidence}"""


def pushes(pr):
    """A PR's pushed heads that got checks, oldest first, each as {check: (failed, workflow run id)}.
    Only a push's last commit gets checks, so a commit without any was pushed along with a later one."""
    heads = []
    for node in pr["commits"]["nodes"]:
        runs = ((node["commit"]["statusCheckRollup"] or {}).get("contexts") or {}).get("nodes", [])
        checks = {run["name"]: (run["conclusion"] in FAILED, (run["checkSuite"]["workflowRun"] or {}).get("databaseId"))
                  for run in runs if run.get("name")}
        if checks:
            heads.append(checks)
    return heads


def gate_stats(prs):
    """PRs -> (PRs counted, PRs that passed every check on their first push, pushes, {check: [(PR, run id)] of the
    pushes it failed, oldest first}). A PR counts if it merged or came from a factory run: closed experiments don't."""
    rows = [(pr["number"], heads) for pr in prs
            if (pr["merged"] or pr["headRefName"].startswith("factory/")) and (heads := pushes(pr))]
    failures = collections.defaultdict(list)
    for number, heads in rows:
        for checks in heads:
            for name, (failed, run) in checks.items():
                if failed:
                    failures[name].append((number, run))
    first = sum(not any(failed for failed, _ in heads[0].values()) for _, heads in rows)
    return len(rows), first, sum(len(heads) for _, heads in rows), dict(failures)


def top_problem(failures):
    """The check that failed the most pushes; a tie goes to the one that failed the newest PR."""
    # shortcut: only gate checks compete; once factory runs outnumber hand-made PRs, also rank failed, timed-out and errored runs.
    return max(failures, key=lambda check: (len(failures[check]), failures[check][-1][0]), default=None)


def block_reasons(review):
    """A review's verdict: the lines after its last **BLOCK**, else its last three lines. None if the reviewer crashed."""
    if review.startswith(REVIEW_NOT_RUN):
        return None
    verdict = review.rsplit("**BLOCK**", 1)[1] if "**BLOCK**" in review else "\n".join(review.splitlines()[-3:])
    lines = [line.strip().removeprefix("- ") for line in verdict.splitlines() if line.strip()]
    return " ".join(lines)[:REASON_LIMIT] or None


def run_stats(metas):
    """Factory run records -> (count by status of the finished runs, completed on their first build, median minutes
    from start to finish, [(run id, status, why)] for the runs that did not complete)."""
    ended = [meta for meta in metas if meta.get("finished_at")]
    statuses = collections.Counter(meta["status"] for meta in ended)
    first = sum(meta["status"] == "completed" and meta.get("attempt") == 0 for meta in ended)
    minutes = [(meta["finished_at"] - meta["started_at"]) / 60 for meta in ended if "started_at" in meta]
    missed = [(meta["run_id"], meta["status"], meta.get("blocking_reason") or meta.get("error") or f"exit code {meta.get('exit_code')}")
              for meta in ended if meta["status"] != "completed"]
    return statuses, first, statistics.median(minutes) if minutes else None, missed


def evidence(check, failures):
    """[(PR, block reasons or None)] for the latest failures of `check`, skipping reviews whose reviewer crashed."""
    quotes = []
    for number, run in reversed(failures):
        if len(quotes) == EVIDENCE:
            break
        if check not in REVIEWED or not run:
            quotes.append((number, None))
            continue
        with tempfile.TemporaryDirectory() as tmp:
            got = gh("run", "download", str(run), "-n", f"review-{check}", "-D", tmp, check=False)
            review = pathlib.Path(tmp, "review.md")
            text = review.read_text() if got.returncode == 0 and review.exists() else ""  # artifacts expire after 90 days
        if text.startswith(REVIEW_NOT_RUN):
            continue
        quotes.append((number, block_reasons(text) if text else None))
    return quotes


def proposal(check, failures, prs, pushed, quotes):
    """The issue's title and body for the top problem."""
    count = len(failures[check])
    rate = count / prs
    listed = "\n".join(f"- #{number}: {reasons}" if reasons else f"- #{number}" for number, reasons in quotes)
    task = TASK.format(check=check, prs=prs, count=count, evidence=listed)
    body = f"""## Problem
`{check}` failed {count} of {pushed} pushes across the last {prs} PRs, the most of any check ({rate:.2f} per PR).

## Evidence
{listed}

## Proposed task
To approve, send this task to the factory (factory/intake/README.md), then close this issue with a link to its PR.

```
{task}
```

## Measure
After 10 more PRs, run `factory/qa/kaizen_report.py --prs 10`. It worked if `{check}` fails fewer than {rate:.2f} pushes per PR."""
    return f"Kaizen: cut the rework {check} causes", body


def file_issue(title, body):
    """Open the proposal as a kaizen issue, unless one is still open."""
    waiting = json.loads(gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number,title").stdout)
    if waiting:
        print(f"Not filed: #{waiting[0]['number']} ({waiting[0]['title']}) is still open, and one improvement runs at a time.")
        return
    gh("label", "create", LABEL, "--color", "0E8A16", "--description", "Kaizen proposal waiting for operator approval", "--force")
    print(f"Filed {gh('issue', 'create', '--title', title, '--label', LABEL, '--body', body).stdout.strip()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prs", type=int, default=40, help="how many of the latest PRs to read (at most 100)")
    parser.add_argument("--file", action="store_true", help="open the proposal as a kaizen issue")
    args = parser.parse_args()

    repo = json.loads(gh("repo", "view", "--json", "owner,name").stdout)
    data = json.loads(gh("api", "graphql", "-f", f"query={QUERY}", "-F", f"owner={repo['owner']['login']}",
                         "-F", f"name={repo['name']}", "-F", f"n={min(args.prs, 100)}").stdout)
    prs, first, pushed, failures = gate_stats(data["data"]["repository"]["pullRequests"]["nodes"])
    print(f"Gate: {prs} of the last {args.prs} PRs count (merged, or from a factory run), with {pushed} pushes")
    print(f"  passed every check on the first push: {first} of {prs}")
    print(f"  {'check':18} failed pushes  per PR")
    for check, failed in sorted(failures.items(), key=lambda kv: -len(kv[1])):
        print(f"  {check:18} {len(failed):13}  {len(failed) / prs:.2f}")

    statuses, first_build, minutes, missed = run_stats(json.loads(path.read_text()) for path in LOG_DIR.glob("*.meta.json"))
    print(f"Factory runs: {sum(statuses.values())} finished ({', '.join(f'{n} {s}' for s, n in statuses.most_common())})")
    if minutes is not None:
        print(f"  completed on the first build: {first_build}; median {minutes:.0f} minutes from start to finish")
    for run_id, status, why in missed:
        print(f"  {run_id} {status}: {why}")

    check = top_problem(failures)
    if check is None:
        print("\nNo check failed a push. Nothing to propose.")
    else:
        title, body = proposal(check, failures, prs, pushed, evidence(check, failures[check]))
        print(f"\n# {title}\n\n{body}")
        if args.file:
            file_issue(title, body)
