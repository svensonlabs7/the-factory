# Uses Claude Code (claude -p) with Pro subscription — no API key required

"""
Webhook adapter for The Factory intake pipeline.
Receives tasks via HTTP, spawns `claude -p` in headless mode, and tracks run state.

Endpoints:
  POST /trigger   — start a new factory run
  GET  /status/:run_id — poll run state
  GET  /health    — liveness check
"""

import hashlib
import hmac
import json
import logging
import os
import shlex
import shutil
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = os.environ.get("FACTORY_WEBHOOK_SECRET", "")
# Agents run with permission prompts off, so an unsigned trigger would be remote code execution.
if not WEBHOOK_SECRET:
    raise RuntimeError("FACTORY_WEBHOOK_SECRET must be set")
FACTORY_ROOT = Path(os.environ.get("FACTORY_ROOT", "/Users/labs/projects/the-factory"))
# Runs the agent in an OpenHands Docker sandbox. Called as: <command> <workdir> <prompt> <timeout-seconds>.
AGENT_CMD = shlex.split(os.environ.get("FACTORY_AGENT_CMD", f"uv run -q --script {FACTORY_ROOT}/factory/build/run_agent.py"))
AGENT_TIMEOUT = 1800  # 30-minute cap. The agent gets a shorter limit so it can end itself and remove its container.
GH_BIN = os.environ.get("GH_BIN", "gh")
LOG_DIR = FACTORY_ROOT / ".factory-logs"
# Each run gets its own clone here, under the home directory because the Docker VM mounts only that.
RUNS_DIR = FACTORY_ROOT.parent / "the-factory-runs"
HEARTBEAT_FILE = FACTORY_ROOT / "HEARTBEAT.md"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("factory.intake")

# ---------------------------------------------------------------------------
# In-memory run store  (replace with a DB for persistence)
# ---------------------------------------------------------------------------

runs: dict[str, dict] = {}
# One run at a time, in arrival order: runs share one Claude plan quota and one origin.
RUN_EXECUTOR = ThreadPoolExecutor(max_workers=1)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Factory Intake", version="1.0.0")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TriggerPayload(BaseModel):
    task: str
    branch: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    priority: Optional[str] = "normal"


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, sig_header: str) -> bool:
    """Return True if the X-Hub-Signature-256 header matches WEBHOOK_SECRET."""
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


# ---------------------------------------------------------------------------
# Task prompt builder
# ---------------------------------------------------------------------------

TASK_PROMPT_TEMPLATE = """\
/poteto-mode {user_task}

Follow the ponytail skill: the smallest change that fully solves the task.
You are in a git repository on branch {branch}. When you are done, run: git add -A && git commit -m "factory: {run_id}"
Do not push or open a PR, and skip any playbook step that does. The factory publishes your branch.
"""


def _build_prompt(user_task: str, branch: str, run_id: str) -> str:
    return TASK_PROMPT_TEMPLATE.format(user_task=user_task, branch=branch, run_id=run_id)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run(*cmd: str, cwd: Path = FACTORY_ROOT) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(cmd)}: {result.stderr.strip()}")
    return result.stdout.strip()


@contextmanager
def _checkout(run_id: str, branch: str):
    """A private clone for the sandbox, so it never sees the checkout the service runs from."""
    workdir = RUNS_DIR / run_id
    _run("git", "clone", "--quiet", "--branch", "main", _run("git", "remote", "get-url", "origin"), str(workdir))
    _run("git", "checkout", "-b", branch, cwd=workdir)
    for key in ("user.name", "user.email"):
        _run("git", "config", key, _run("git", "config", key), cwd=workdir)
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _publish(branch: str, body: str, workdir: Path) -> str:
    """Push and open the PR from the trusted checkout. The sandbox holds no GitHub credentials, and git run
    inside the agent's clone would execute whatever hooks and config the agent wrote there. The fetch only
    reads objects from that clone. Runs go one at a time, so FETCH_HEAD is safe to use."""
    _run("git", "fetch", "--quiet", "origin", "main")
    _run("git", "fetch", "--quiet", str(workdir), branch)
    if _run("git", "rev-list", "--count", "origin/main..FETCH_HEAD") == "0":
        raise RuntimeError("agent made no commits")
    _run("git", "push", "origin", f"FETCH_HEAD:refs/heads/{branch}")
    return _run(GH_BIN, "pr", "create", "--head", branch, "--base", "main", "--title", branch, "--body", body)


def _finish(run_id: str, status: str, **fields) -> None:
    runs[run_id].update(status=status, finished_at=time.time(), **fields)
    _update_heartbeat(run_id, status.upper())
    log.info("Run %s %s", run_id, status)


def _run_agent(run_id: str, prompt: str, branch: str) -> None:
    log_file = LOG_DIR / f"{run_id}.log"
    runs[run_id]["status"] = "running"
    runs[run_id]["started_at"] = time.time()

    _update_heartbeat(run_id, "RUNNING")

    log.info("Starting the sandboxed agent for run %s", run_id)

    try:
        with _checkout(run_id, branch) as workdir, open(log_file, "w") as lf:
            result = subprocess.run(
                [*AGENT_CMD, str(workdir), prompt, str(AGENT_TIMEOUT - 300)],
                stdout=lf,
                stderr=subprocess.STDOUT,
                timeout=AGENT_TIMEOUT,
            )
            if result.returncode:
                _finish(run_id, "failed", exit_code=result.returncode)
            else:
                body = f"Factory build {run_id}\n\nTask: {runs[run_id]['task'][:200]}"
                _finish(run_id, "completed", pr_url=_publish(branch, body, workdir))
    except subprocess.TimeoutExpired:
        _finish(run_id, "timeout")
    except Exception as exc:
        log.exception("Run %s failed with exception: %s", run_id, exc)
        _finish(run_id, "error", error=str(exc))


def _update_heartbeat(run_id: str, status: str) -> None:
    try:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        content = f"# Factory Heartbeat\n\nLast run: `{run_id}`\nStatus: **{status}**\nTimestamp: {ts}\n"
        HEARTBEAT_FILE.write_text(content)
    except Exception:
        log.exception("Failed to update HEARTBEAT.md")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/trigger", status_code=202)
async def trigger(request: Request):
    body = await request.body()

    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload_data = json.loads(body)
        payload = TriggerPayload(**payload_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    run_id = str(uuid.uuid4())[:8]
    branch = payload.branch or f"factory/{run_id}"
    prompt = _build_prompt(payload.task, branch, run_id)

    runs[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "branch": branch,
        "task": payload.task,
        "queued_at": time.time(),
    }

    log.info("Queued run %s: branch=%s", run_id, branch)
    RUN_EXECUTOR.submit(_run_agent, run_id, prompt, branch)

    return JSONResponse(
        status_code=202,
        content={"run_id": run_id, "branch": branch, "status": "queued"},
    )


@app.get("/status/{run_id}")
async def status(run_id: str):
    run = runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/health")
async def health():
    return {"status": "ok", "runs_in_memory": len(runs)}
