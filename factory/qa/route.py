#!/usr/bin/env python3
"""Print the systems checks a diff triggers: open gaps in the code it touches, load assumptions it changes, and the
review-checklist items of the cards whose Triggers line it hits. Stdlib only, so builders and CI run it as is.

Usage: route.py [git-range]
  No range: the working tree, untracked files included, against its merge base with origin/HEAD, origin/main or main.
  A range (for example origin/main...pr-head): that diff only.

The output is built only from knowledge/systems in this checkout, never from the diff's text, so a PR cannot put
words in front of its reviewer.
"""
import pathlib
import re
import subprocess
import sys
from typing import List, NamedTuple, Optional, Pattern

KS = pathlib.Path(__file__).resolve().parents[2] / "knowledge" / "systems"
NOT_CODE = re.compile(r"^(knowledge|vendor|tests|\.claude)/|\.md$")  # prose and tests never fire a `lines` trigger
TRIPWIRE = " · tripwire"  # ends the one checklist item a "not needed at this load" card shows
ASSUMPTION = re.compile(r"^- \*\*(.+?)\*\* · where (.+?) · lines `([^`]+)` · re-check ([\d ]+)$", re.M)
MAX_ITEMS, MAX_GAPS, SLACK = 15, 4, 15  # SLACK: lines a gap's recorded location may have drifted
SEVERITY = {"high": 0, "medium": 1, "low": 2}
GIT_TIMEOUT = 60


class Card(NamedTuple):
    name: str
    files: Optional[Pattern]
    lines: Optional[Pattern]
    items: List[str]
    tripwire: List[str]  # the items marked with TRIPWIRE; a card with one shows only that item

    @property
    def number(self):
        return self.name[:3]


def cards():
    """Every card with a Triggers line."""
    out = []
    for path in sorted(KS.glob("[0-9][0-9][0-9]-*.md")):
        text = path.read_text()
        triggers = re.search(r"^Triggers: (.+)$", text, re.M)
        if not triggers:
            continue
        keys = dict(re.findall(r"(files|lines) `([^`]+)`", triggers.group(1)))
        checklist = re.search(r"## Review checklist\n(.*?)\n## ", text, re.S)
        items = re.findall(r"^- \[ \] .+$", checklist.group(1), re.M) if checklist else []
        out.append(Card(path.name, re.compile(keys["files"]) if "files" in keys else None,
                        re.compile(keys["lines"]) if "lines" in keys else None,
                        items, [item for item in items if item.endswith(TRIPWIRE)]))
    return out


def assumption_entries():
    """[(name, where, lines regex, [card numbers])] from ASSUMPTIONS.md."""
    return [(name, where, regex, nums.split())
            for name, where, regex, nums in ASSUMPTION.findall((KS / "ASSUMPTIONS.md").read_text())]


def parse(diff):
    """{path: (changed lines, [(old first line, old last line)])} from `git diff -U0` output."""
    changes, path = {}, None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/.+? b/(.+)$", line)
            path = match.group(1) if match else None
            if path:
                changes.setdefault(path, ([], []))
        elif path is None or line.startswith(("--- a/", "--- /dev/null", "+++ b/", "+++ /dev/null")):
            continue
        elif line.startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? ", line)
            start, count = int(match.group(1)), int(match.group(2) or 1)
            changes[path][1].append((start, start + max(count, 1) - 1))
        elif line[:1] in ("+", "-"):
            changes[path][0].append(line[1:])
    return changes


def code_lines(changes):
    return [line for path, (lines, _) in changes.items() if not NOT_CODE.search(path) for line in lines]


def gaps(changes):
    """Open GAPS.md rows whose recorded file (and line range, when it has one) this diff touches."""
    hits = []
    for row in (KS / "GAPS.md").read_text().splitlines():
        cells = [cell.strip() for cell in row.strip().strip("|").split(" | ")]
        if len(cells) < 5 or cells[-1] != "open":
            continue
        topic, where, scenario, severity = cells[0], cells[1], " | ".join(cells[2:-2]), cells[-2]
        for ref in re.findall(r"`([^`]+)`", where):
            file, _, spec = ref.partition(":")
            if file not in changes:
                continue
            spans = []
            for part in re.findall(r"\d+(?:-\d+)?", spec):
                lo, _, hi = part.partition("-")
                spans.append((int(lo), int(hi or lo)))
            near = any(lo - SLACK <= end and start <= hi + SLACK for lo, hi in spans for start, end in changes[file][1])
            if not spans or near:
                summary = scenario.split(". ")[0][:220]
                hits.append((SEVERITY.get(severity, 3), f"- **[{severity}] {topic}** at `{ref}`: {summary}."))
                break
    return [line for _, line in sorted(hits)][:MAX_GAPS]


def assumptions(changes, all_cards):
    """Load assumptions whose `lines` regex a changed line matches, with the cards to re-check."""
    names = {card.number: card.name for card in all_cards}
    lines = code_lines(changes)
    return [f"- **{name}** ({where}): re-check " + ", ".join(names[n] for n in nums)
            for name, where, regex, nums in assumption_entries() if any(re.search(regex, line) for line in lines)]


def matched(changes, all_cards):
    """[(card, score, items to show)] for the cards whose triggers this diff hits, tripwires first."""
    lines, hits = code_lines(changes), []
    for card in all_cards:
        score = 3 * sum(1 for path in changes if card.files and not path.startswith("knowledge/") and card.files.search(path))
        score += sum(1 for line in lines if card.lines and card.lines.search(line))
        if score:
            hits.append((card, score, card.tripwire or card.items))
    return sorted(hits, key=lambda hit: (not hit[0].tripwire, -hit[1], hit[0].name))


def render(changes):
    all_cards = cards()
    gap_lines, assumed, hits = gaps(changes), assumptions(changes, all_cards), matched(changes, all_cards)
    if not (gap_lines or assumed or hits):
        return "Systems checks: no card in knowledge/systems applies to this diff.\n"
    out = ["## Systems checks for this diff", "",
           "Routed from knowledge/systems by factory/qa/route.py. Check an item only where its 'Applies when' fits the "
           "diff, and block only when its 'Block if' is true. Never block for a technique a card says this load does not "
           "need. Read a card only when you need its reasoning."]
    if gap_lines:
        out += ["", "### Known gaps in the code this diff touches", "These already exist: block only if the diff makes one worse.", *gap_lines]
    if assumed:
        out += ["", "### Load assumptions this diff changes", "These cards' 'not needed here' verdicts assumed the old value.", *assumed]
    shown, rest = 0, []
    for card, _, items in hits:
        if shown + len(items) > MAX_ITEMS and shown:
            rest.append(card.name)
            continue
        out += ["", f"### {card.name}" + (" (tripwire: this load does not need it)" if card.tripwire else ""), *items]
        shown += len(items)
    if rest:
        out += ["", "Also matched, not shown (read only if relevant): " + ", ".join(rest)]
    return "\n".join(out) + "\n"


def collect(rng):
    top = pathlib.Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                                      check=True, timeout=GIT_TIMEOUT).stdout.strip())

    def git(*args):
        return subprocess.run(["git", *args], cwd=top, capture_output=True, text=True, check=True, timeout=GIT_TIMEOUT).stdout

    if rng:
        return parse(git("diff", "-U0", "--no-color", "--no-ext-diff", rng))
    base = "HEAD"
    for ref in ("origin/HEAD", "origin/main", "main"):
        found = subprocess.run(["git", "merge-base", "HEAD", ref], cwd=top, capture_output=True, text=True, timeout=GIT_TIMEOUT)
        if found.returncode == 0:
            base = found.stdout.strip()
            break
    changes = parse(git("diff", "-U0", "--no-color", "--no-ext-diff", base))
    for name in filter(None, git("ls-files", "--others", "--exclude-standard", "-z").split("\0")):
        try:
            changes[name] = ((top / name).read_text().splitlines(), [])
        except (OSError, UnicodeDecodeError):
            continue  # a binary or unreadable file has no lines to match
    return changes


if __name__ == "__main__":
    sys.stdout.write(render(collect(sys.argv[1] if len(sys.argv) > 1 else None)))
