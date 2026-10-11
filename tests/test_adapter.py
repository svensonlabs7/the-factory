import hashlib
import hmac
import importlib
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

SECRET = "test-secret"
GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def sign(body: bytes) -> dict:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


FAKE_AGENT = """#!/bin/sh
cd "$1" || exit 1
echo "cwd=$PWD branch=$(git branch --show-current)"
echo "prompt-start=$(printf '%s' "$2" | head -c 13)"
case "$2" in *DUPLICATED-HELPER*) echo "retry-saw-findings";; esac
if [ -n "$FAKE_HOOK_MARKER" ]; then
    printf '#!/bin/sh\\ntouch "%s"\\n' "$FAKE_HOOK_MARKER" > .git/hooks/pre-push
    chmod +x .git/hooks/pre-push
fi
if [ "${FAKE_COMMIT:-1}" = 1 ]; then
    echo "change $$" > change.txt
    git add -A
    git commit -q -m fake
fi
sleep "${FAKE_SLEEP:-0}"
exit "${FAKE_EXIT:-0}"
"""


FAKE_GH = """#!/usr/bin/env python3
import json, os, pathlib, sys

state = pathlib.Path(os.environ["FAKE_GH_STATE"])
args = sys.argv[1:]
if args[:2] == ["pr", "create"]:
    (state / "pr-creates").open("a").write("x")
    print("https://example.invalid/pull/1")
elif args[0] == "api":
    print("thermo-nuclear\\ntests\\nponytail-review")
elif args[:2] == ["pr", "checks"]:
    rounds = os.environ.get("FAKE_CHECKS", "pass").split(",")
    calls = state / "check-calls"
    calls.open("a").write("x")
    failing = rounds[min(len(calls.read_text()) - 1, len(rounds) - 1)]
    names = ["thermo-nuclear", "tests", "ponytail-review"]
    print(json.dumps([{"name": n, "bucket": "fail" if n == failing else "pass"} for n in names]))
elif args[:2] == ["run", "list"]:
    print(json.dumps([{"databaseId": 7, "name": "qa-gate", "conclusion": "failure"}]))
elif args[:2] == ["run", "download"]:
    out = pathlib.Path(args[args.index("--dir") + 1]) / "review-thermo-nuclear"
    out.mkdir(parents=True)
    (out / "review.md").write_text("DUPLICATED-HELPER in change.txt. BLOCK\\n")
"""

HEARTBEAT = """| Field | Value |
|---|---|
| **last_run** | — |
| **pipeline_status** | idle |
| **build_status** | — |
| **qa_gate_status** | — |
| **last_pr_blocked** | — |
| **blocking_reason** | — |
"""


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    origin, root = tmp_path / "origin.git", tmp_path / "factory"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(root))
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@example.com")
    (root / "README.md").write_text("seed")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    git(root, "push", "-q", "origin", "HEAD:main")

    (root / "HEARTBEAT.md").write_text(HEARTBEAT)
    (tmp_path / "gh-state").mkdir()
    for name, body in (("fake-agent.sh", FAKE_AGENT), ("fake-gh.py", FAKE_GH)):
        (tmp_path / name).write_text(body)
        (tmp_path / name).chmod(0o755)

    monkeypatch.setenv("FACTORY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("FACTORY_ROOT", str(root))
    monkeypatch.setenv("FACTORY_AGENT_CMD", str(tmp_path / "fake-agent.sh"))
    monkeypatch.setenv("GH_BIN", str(tmp_path / "fake-gh.py"))
    monkeypatch.setenv("FAKE_GH_STATE", str(tmp_path / "gh-state"))
    sys.modules.pop("factory.intake.webhook_adapter", None)
    module = importlib.import_module("factory.intake.webhook_adapter")
    monkeypatch.setattr(module, "CHECKS_POLL", 0)
    yield module, root, TestClient(module.app)
    module.RUN_EXECUTOR.shutdown(wait=True)


def trigger(client, **payload):
    import json

    body = json.dumps({"task": "t", **payload}).encode()
    return client.post("/trigger", content=body, headers=sign(body))


def wait_done(client, run_id):
    for _ in range(100):
        run = client.get(f"/status/{run_id}").json()
        if run["status"] not in ("queued", "running", "qa"):
            return run
        time.sleep(0.1)
    raise AssertionError(f"run {run_id} did not finish")


def test_refuses_to_start_without_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTORY_ROOT", str(tmp_path))
    monkeypatch.delenv("FACTORY_WEBHOOK_SECRET", raising=False)
    sys.modules.pop("factory.intake.webhook_adapter", None)
    with pytest.raises(RuntimeError, match="FACTORY_WEBHOOK_SECRET"):
        importlib.import_module("factory.intake.webhook_adapter")


def test_health(adapter):
    _, _, client = adapter
    assert client.get("/health").json()["status"] == "ok"


@pytest.mark.parametrize("headers", [{}, {"X-Hub-Signature-256": "sha256=bad"}])
def test_rejects_unsigned_and_badly_signed_triggers(adapter, headers):
    _, _, client = adapter
    assert client.post("/trigger", content=b'{"task": "t"}', headers=headers).status_code == 401


@pytest.mark.parametrize("body", [b"not json", b'{"branch": "factory/x"}', b'{"task": "t", "branch": "-evil"}'])
def test_rejects_invalid_payloads(adapter, body):
    _, _, client = adapter
    assert client.post("/trigger", content=body, headers=sign(body)).status_code == 422


def test_run_publishes_from_a_private_clone_and_cleans_up(adapter):
    module, root, client = adapter
    run_id = trigger(client).json()["run_id"]
    run = wait_done(client, run_id)

    assert (run["status"], run["pr_url"]) == ("completed", "https://example.invalid/pull/1")
    log = (root / ".factory-logs" / f"{run_id}.log").read_text()
    assert f"cwd={module.RUNS_DIR / f'{run_id}-0'} branch=factory/{run_id}" in log
    assert "prompt-start=/poteto-mode" in log
    assert not any(module.RUNS_DIR.iterdir())
    assert f"refs/heads/factory/{run_id}" in git(root, "ls-remote", "origin")
    assert git(root, "branch", "--show-current") == "main"
    assert git(root, "branch", "--list", "factory/*") == ""


def test_hooks_the_agent_plants_never_run_on_the_host(adapter, tmp_path, monkeypatch):
    _, _, client = adapter
    marker = tmp_path / "hook-ran"
    monkeypatch.setenv("FAKE_HOOK_MARKER", str(marker))
    assert wait_done(client, trigger(client).json()["run_id"])["status"] == "completed"
    assert not marker.exists()


def test_runs_are_serialized_in_arrival_order(adapter, monkeypatch):
    _, _, client = adapter
    monkeypatch.setenv("FAKE_SLEEP", "1")
    first, second = trigger(client).json()["run_id"], trigger(client).json()["run_id"]
    a, b = wait_done(client, first), wait_done(client, second)
    assert b["started_at"] >= a["finished_at"]


def test_failed_agent_reports_exit_code_and_publishes_nothing(adapter, monkeypatch):
    _, root, client = adapter
    monkeypatch.setenv("FAKE_EXIT", "3")
    run = wait_done(client, trigger(client).json()["run_id"])
    assert (run["status"], run["exit_code"]) == ("failed", 3)
    assert "pr_url" not in run
    assert "refs/heads/factory" not in git(root, "ls-remote", "origin")


def test_run_without_commits_is_an_error(adapter, monkeypatch):
    _, _, client = adapter
    monkeypatch.setenv("FAKE_COMMIT", "0")
    run = wait_done(client, trigger(client).json()["run_id"])
    assert run["status"] == "error" and "no commits" in run["error"]


def test_reused_branch_is_rejected_and_the_next_run_still_runs(adapter):
    _, _, client = adapter
    first = wait_done(client, trigger(client, branch="factory/dupe").json()["run_id"])
    second = wait_done(client, trigger(client, branch="factory/dupe").json()["run_id"])
    third = wait_done(client, trigger(client).json()["run_id"])
    assert first["status"] == "completed"
    assert second["status"] == "error" and "rejected" in second["error"]
    assert third["status"] == "completed"


def test_a_blocked_pr_gets_a_fresh_builder_with_the_findings_then_passes(adapter, monkeypatch):
    module, root, client = adapter
    monkeypatch.setenv("FAKE_CHECKS", "thermo-nuclear,pass")
    run_id = trigger(client).json()["run_id"]
    run = wait_done(client, run_id)

    assert (run["status"], run["attempt"]) == ("completed", 1)
    log = (root / ".factory-logs" / f"{run_id}.log").read_text()
    assert log.count("===== attempt") == 2 and log.count("retry-saw-findings") == 1
    assert (root.parent / "gh-state" / "pr-creates").read_text() == "x"
    assert git(root, "rev-list", "--count", f"origin/main..origin/factory/{run_id}") == "2"
    assert "| **pipeline_status** | idle |" in (root / "HEARTBEAT.md").read_text()


def test_a_pr_that_stays_blocked_escalates_after_two_fix_rounds(adapter, monkeypatch):
    _, root, client = adapter
    monkeypatch.setenv("FAKE_CHECKS", "thermo-nuclear")
    run_id = trigger(client).json()["run_id"]
    run = wait_done(client, run_id)

    assert (run["status"], run["attempt"]) == ("blocked", 2)
    assert "thermo-nuclear still failing after 2 fix rounds" in run["blocking_reason"]
    assert (root / ".factory-logs" / f"{run_id}.log").read_text().count("===== attempt") == 3
    heartbeat = (root / "HEARTBEAT.md").read_text()
    assert "| **pipeline_status** | blocked |" in heartbeat
    assert "| **last_pr_blocked** | https://example.invalid/pull/1 |" in heartbeat
    assert "thermo-nuclear still failing" in heartbeat


def test_a_pr_that_passes_first_time_is_not_retried(adapter):
    _, root, client = adapter
    run_id = trigger(client).json()["run_id"]
    run = wait_done(client, run_id)
    assert (run["status"], run["attempt"]) == ("completed", 0)
    assert (root / ".factory-logs" / f"{run_id}.log").read_text().count("===== attempt") == 1
