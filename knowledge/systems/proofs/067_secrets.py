"""Secrets management: does anything stop a sandboxed agent's commit from carrying a secret out?
The real adapter (fixture), with an agent that commits a FAKE, randomly generated Anthropic-format key.
1. The adapter pushes it to origin: the egress lock-down covers the network, not the commits it publishes.
2. gitleaks, run on the pushed commit, flags it: a scan before the push would have stopped it."""
import json
import secrets
import string
import subprocess

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)

FAKE_KEY = "sk-ant-api03-" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(93)) + "AA"


def test_secret_in_agent_commit(adapter, tmp_path, monkeypatch):
    module, root, client = adapter
    agent = tmp_path / "leaky-agent.sh"
    agent.write_text(f"""#!/bin/sh
cd "$1" || exit 1
printf 'debug: CLAUDE_CODE_OAUTH_TOKEN=%s\\n' '{FAKE_KEY}' > debug.log
git add -A && git commit -q -m "factory: debug output"
""")
    agent.chmod(0o755)
    monkeypatch.setattr(module, "AGENT_CMD", [str(agent)])
    run = wait_done(client, trigger(client).json()["run_id"])
    origin = tmp_path / "origin.git"
    branch = run["branch"]
    published = subprocess.run(["git", "-C", str(origin), "show", f"{branch}:debug.log"], capture_output=True, text=True).stdout
    print(f"\n1  run {run['status']}; origin's {branch} has debug.log carrying the fake key: {FAKE_KEY in published}")
    report = tmp_path / "leaks.json"
    scan = subprocess.run(["gitleaks", "git", "--no-banner", "--redact", "--report-format", "json", "--report-path", str(report),
                           f"--log-opts=-1 {branch}", str(origin)], capture_output=True, text=True)
    found = json.loads(report.read_text() or "[]")
    print(f"2  gitleaks on that commit: exit {scan.returncode}, findings {[(f['RuleID'], f['File']) for f in found]}")
