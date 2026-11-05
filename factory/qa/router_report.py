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

# Reviews cite a card as "011-timeouts.md", "011-timeouts" or "**033 Leader election**", so match its number.
CITED = re.compile(r"\b(\d{3})(?=-[a-z]|\s+[A-Z][a-z])")
GH_TIMEOUT = 120
NARROW, WIDEN = 5, 2  # routed this often and never cited: narrow; cited this often unrouted: widen
KS = pathlib.Path(__file__).resolve().parents[2] / "knowledge" / "systems"


def tally(pairs, known=None):
    """pairs: [(systems.md text, review.md text)] -> {card number: [routed, cited when routed, cited when not routed]}.
    known: the real card numbers; a review's "HTTP 404 Not found" is then not counted as citing card 404."""
    counts = collections.defaultdict(lambda: [0, 0, 0])
    for systems, review in pairs:
        routed = set(re.findall(r"^### (\d{3})-", systems, re.M))
        cited = {n for n in CITED.findall(review) if known is None or n in known}
        for card in routed:
            counts[card][0] += 1
            counts[card][1] += card in cited
        for card in cited - routed:
            counts[card][2] += 1
    return counts


def advice(counts):
    """The trigger changes the evidence supports, by the NARROW and WIDEN rules; none until a card has enough samples."""
    narrow = sorted(card for card, (routed, cited, _) in counts.items() if routed >= NARROW and not cited)
    widen = sorted(card for card, (_, _, missed) in counts.items() if missed >= WIDEN)
    return narrow, widen


def gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check, timeout=GH_TIMEOUT)


def fetch(runs):
    pairs = []
    ids = [run["databaseId"] for run in json.loads(gh("run", "list", "--workflow", "qa-gate.yml", "--limit", str(runs), "--json", "databaseId").stdout)]
    for run_id in ids:
        with tempfile.TemporaryDirectory() as tmp:
            got = gh("run", "download", str(run_id), "-n", "review-thermo-nuclear", "-D", tmp, check=False)
            systems, review = pathlib.Path(tmp, "systems.md"), pathlib.Path(tmp, "review.md")
            if got.returncode == 0 and systems.exists() and review.exists():  # runs before the router have no systems.md
                pairs.append((systems.read_text(), review.read_text()))
    return pairs


if __name__ == "__main__":
    pairs = fetch(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
    print(f"{len(pairs)} reviews with routed checks")
    names = {path.name[:3]: path.name for path in KS.glob("[0-9][0-9][0-9]-*.md")}
    counts = tally(pairs, set(names))
    print(f"{'card':40} routed  cited  cited-unrouted")
    for card, (routed, cited, missed) in sorted(counts.items(), key=lambda kv: (-kv[1][0], kv[0])):
        print(f"{names.get(card, card):40} {routed:6} {cited:6} {missed:15}")
    narrow, widen = advice(counts)
    print(f"narrow these triggers (routed {NARROW}+ times, never cited): {', '.join(names.get(c, c) for c in narrow) or 'none yet'}")
    print(f"widen these triggers (cited {WIDEN}+ times unrouted): {', '.join(names.get(c, c) for c in widen) or 'none yet'}")
