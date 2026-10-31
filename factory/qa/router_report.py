#!/usr/bin/env python3
"""How well route.py's picks match what reviewers use. For recent QA gate runs it reads the thermo-nuclear artifact
(systems.md, the routed checks, and review.md, the review) and counts, per card, how often it was routed and how
often the review cited it. A card routed often and never cited has a trigger to narrow; a card cited but not routed
has a trigger to widen. Usage: factory/qa/router_report.py [runs, default 30]"""
import collections
import json
import pathlib
import re
import subprocess
import sys
import tempfile

CARD = re.compile(r"\b\d{3}-[a-z0-9-]+\.md\b")
GH_TIMEOUT = 120


def tally(pairs):
    """pairs: [(systems.md text, review.md text)] -> {card: [routed, cited when routed, cited when not routed]}."""
    counts = collections.defaultdict(lambda: [0, 0, 0])
    for systems, review in pairs:
        routed = set(re.findall(r"^### (\d{3}-[a-z0-9-]+\.md)", systems, re.M))
        cited = set(CARD.findall(review))
        for card in routed:
            counts[card][0] += 1
            counts[card][1] += card in cited
        for card in cited - routed:
            counts[card][2] += 1
    return counts


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True, timeout=GH_TIMEOUT).stdout


def fetch(runs):
    pairs = []
    ids = [run["databaseId"] for run in json.loads(gh("run", "list", "--workflow", "qa-gate.yml", "--limit", str(runs), "--json", "databaseId"))]
    for run_id in ids:
        with tempfile.TemporaryDirectory() as tmp:
            got = subprocess.run(["gh", "run", "download", str(run_id), "-n", "review-thermo-nuclear", "-D", tmp],
                                 capture_output=True, text=True, timeout=GH_TIMEOUT)
            systems, review = pathlib.Path(tmp, "systems.md"), pathlib.Path(tmp, "review.md")
            if got.returncode == 0 and systems.exists() and review.exists():  # runs before the router have no systems.md
                pairs.append((systems.read_text(), review.read_text()))
    return pairs


if __name__ == "__main__":
    pairs = fetch(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
    print(f"{len(pairs)} reviews with routed checks")
    rows = sorted(tally(pairs).items(), key=lambda kv: (-kv[1][0], kv[0]))
    print(f"{'card':40} routed  cited  cited-unrouted")
    for card, (routed, cited, missed) in rows:
        print(f"{card:40} {routed:6} {cited:6} {missed:15}")
