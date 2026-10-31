#!/usr/bin/env python3
"""Zero-token checks compiled from the knowledge/systems cards: the checklist items a machine can decide alone.
Each finding names the card that argues it. Exits 1 on any finding. Stdlib only."""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SUBPROCESS = {"run", "call", "check_call", "check_output"}


def python_rules(text):
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "subprocess"
                and func.attr in SUBPROCESS and not any(k.arg == "timeout" for k in node.keywords)):
            yield node.lineno, f"subprocess.{func.attr} without timeout= (011-timeouts.md)"
        if any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
            yield node.lineno, "shell=True runs a string through the shell (078-sql-injection.md)"


def workflow_rules(text):
    for number, line in enumerate(text.splitlines(), 1):
        used = re.match(r"\s*(?:-\s*)?uses:\s*([^\s#]+)", line)
        if used and not used.group(1).startswith("./") and not re.search(r"@[0-9a-f]{40}$", used.group(1)):
            yield number, f"{used.group(1)} is not pinned to a commit SHA (108-dependency-hell.md)"


def html_rules(text):
    for number, line in enumerate(text.splitlines(), 1):
        if re.search(r"\.(innerHTML|outerHTML)\s*\+?=|insertAdjacentHTML|document\.write\(", line):
            yield number, "builds HTML from a string; use textContent or DOM nodes (079-xss.md)"


RULES = [("factory/**/*.py", python_rules), (".github/workflows/*.yml", workflow_rules),
         ("factory/**/*.html", html_rules), ("factory/**/*.js", html_rules)]


def findings(root=ROOT):
    for pattern, rule in RULES:
        for path in sorted(root.glob(pattern)):
            for number, message in rule(path.read_text()):
                yield f"{path.relative_to(root)}:{number}: {message}"


if __name__ == "__main__":
    found = list(findings())
    print("\n".join(found) or "rules: no findings")
    sys.exit(1 if found else 0)
