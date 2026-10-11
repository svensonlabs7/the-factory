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

    for name, body in (("fake-agent.sh", FAKE_AGENT), ("fake-gh.sh", '#!/bin/sh\necho "https://example.invalid/pull/1"\n')):
        (tmp_path / name).write_text(body)
        (tmp_path / name).chmod(0o755)

    monkeypatch.setenv("FACTORY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("FACTORY_ROOT", str(root))
    monkeypatch.setenv("FACTORY_AGENT_CMD", str(tmp_path / "fake-agent.sh"))
    monkeypatch.setenv("GH_BIN", str(tmp_path / "fake-gh.sh"))
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


def test_run_publishes_from_a_private_clone_and_cleans_up(adapter):
    module, root, client = adapter
    run_id = trigger(client).json()["run_id"]
    run = wait_done(client, run_id)

    assert (run["status"], run["pr_url"]) == ("completed", "https://example.invalid/pull/1")
    log = (root / ".factory-logs" / f"{run_id}.log").read_text()
    assert f"cwd={module.RUNS_DIR / run_id} branch=factory/{run_id}" in log
    assert "prompt-start=/poteto-mode" in log
    assert not (module.RUNS_DIR / run_id).exists()
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
