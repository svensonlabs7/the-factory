"""Observability test: ask new questions of the factory's existing telemetry, without adding instrumentation.
Each question is answered from .factory-logs (meta, actions, logs, rejected.jsonl) or marked unanswerable, with why."""
import collections
import glob
import json
import re
import statistics
import sys

L = sys.argv[1]
metas = [json.load(open(p)) for p in glob.glob(f"{L}/*.meta.json")]
actions = {p.split("/")[-1][:8]: [json.loads(l) for l in open(p)] for p in glob.glob(f"{L}/*.actions.jsonl")}
answers = []


def ask(q, verdict, answer):
    answers.append(verdict)
    print(f"[{verdict:<7}] {q}\n          {answer}")


waits = [(m["started_at"] - m["queued_at"]) / 60 for m in metas if m.get("started_at")]
ask("How long do runs wait in the queue?", "yes", f"median {statistics.median(waits):.1f} min, max {max(waits):.1f} min (meta.json)")

blocked_by = collections.Counter(c for evs in actions.values() for e in evs if e["event"] == "gate_result"
                                 for c, r in e["checks"].items() if r == "fail")
ask("Which gate check blocks most often?", "partial",
    f"action log covers {len(actions)}/{len(metas)} runs: {dict(blocked_by) or 'no failures recorded'}; older runs need the GitHub API, while artifacts last")

ask("Which task wording ends in blocked or failed runs?", "yes",
    "; ".join(f"{m['status']}: {m['task'][:40]!r}" for m in metas if m['status'] != 'completed'))

rej = [json.loads(l) for l in open(f"{L}/rejected.jsonl")]
ask("When were requests rejected, and why?", "yes", f"{len(rej)} entries with time and reason: {dict(collections.Counter(r['reason'] for r in rej))}")

ask("At what time did each accepted /trigger arrive, from which address?", "partial",
    "time yes (meta queued_at); source address no: the access log has it but no timestamps to join on")

ask("How often does the plan usage limit pause the factory?", "no", "no event is written for a pause (061-metrics.md); grepping logs over-counts 3x")

tok = sum(1 for p in glob.glob(f"{L}/[0-9a-f]*.log") for l in open(p, errors="ignore") if "Tokens:" in l and not re.search(r"input \(total 0\).*output \(total 0\)", l))
ask("How much plan usage does one run consume?", "no", f"every 'Tokens:' line in every run log reports 0 (non-zero lines: {tok}); the agent integration does not pass usage back")

ask("Did a timed-out run leave a container behind?", "no", "container start/stop is not recorded per run; only `docker ps` now can tell")

c = collections.Counter(answers)
print(f"\nanswerable from existing telemetry: yes {c['yes']}, partial {c['partial']}, no {c['no']} (of {len(answers)})")
