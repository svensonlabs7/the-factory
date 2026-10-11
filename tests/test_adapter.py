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
    subprocess.run(["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True)


def sign(body: bytes) -> dict:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    origin, root = tmp_path / "origin.git", tmp_path / "factory"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(root))
    (root / "README.md").write_text("seed")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    git(root, "push", "-q", "origin", "HEAD:main")

    fake = tmp_path / "fake-claude.sh"
    fake.write_text('#!/bin/sh\necho "cwd=$PWD branch=$(git branch --show-current)"\nsleep "${FAKE_SLEEP:-0}"\nexit "${FAKE_EXIT:-0}"\n')
    fake.chmod(0o755)

    monkeypatch.setenv("FACTORY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("FACTORY_ROOT", str(root))
    monkeypatch.setenv("CLAUDE_BIN", str(fake))
    sys.modules.pop("factory.intake.webhook_adapter", None)
    module = importlib.import_module("factory.intake.webhook_adapter")
    yield module, root, TestClient(module.app)
    module.RUN_EXECUTOR.shutdown(wait=True)


def trigger(client, **payload):
    import json

    body = json.dumps({"task": "t", **payload}).encode()
    return client.post("/trigger", content=body, headers=sign(body))


def wait_done(client, run_id):
    for _ in range(100):
        run = client.get(f"/status/{run_id}").json()
        if run["status"] not in ("queued", "running"):
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


def test_run_executes_in_its_own_worktree_and_cleans_up(adapter):
    module, root, client = adapter
    run_id = trigger(client).json()["run_id"]
    run = wait_done(client, run_id)

    assert run["status"] == "completed"
    log = (root / ".factory-logs" / f"{run_id}.log").read_text()
    assert f"cwd={module.WORKTREE_DIR / run_id} branch=factory/{run_id}" in log
    assert not (module.WORKTREE_DIR / run_id).exists()
    assert subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True).stdout.strip() == "main"


def test_runs_are_serialized_in_arrival_order(adapter, monkeypatch):
    _, _, client = adapter
    monkeypatch.setenv("FAKE_SLEEP", "1")
    first, second = trigger(client).json()["run_id"], trigger(client).json()["run_id"]
    a, b = wait_done(client, first), wait_done(client, second)
    assert b["started_at"] >= a["finished_at"]


def test_failed_run_reports_exit_code(adapter, monkeypatch):
    _, _, client = adapter
    monkeypatch.setenv("FAKE_EXIT", "3")
    run = wait_done(client, trigger(client).json()["run_id"])
    assert (run["status"], run["exit_code"]) == ("failed", 3)


def test_reused_branch_reports_git_error_and_next_run_still_runs(adapter):
    _, _, client = adapter
    first = wait_done(client, trigger(client, branch="factory/dupe").json()["run_id"])
    second = wait_done(client, trigger(client, branch="factory/dupe").json()["run_id"])
    third = wait_done(client, trigger(client).json()["run_id"])
    assert first["status"] == "completed"
    assert second["status"] == "error" and "already exists" in second["error"]
    assert third["status"] == "completed"
