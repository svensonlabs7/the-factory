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
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = os.environ.get("FACTORY_WEBHOOK_SECRET", "")
FACTORY_ROOT = Path("/Users/labs/projects/the-factory")
LOG_DIR = FACTORY_ROOT / ".factory-logs"
HEARTBEAT_FILE = FACTORY_ROOT / "HEARTBEAT.md"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("factory.intake")

# ---------------------------------------------------------------------------
# In-memory run store  (replace with a DB for persistence)
# ---------------------------------------------------------------------------

runs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Factory Intake", version="1.0.0")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TriggerPayload(BaseModel):
    task: str
    branch: Optional[str] = None
    priority: Optional[str] = "normal"


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, sig_header: str) -> bool:
    """Return True if the X-Hub-Signature-256 header matches WEBHOOK_SECRET."""
    if not WEBHOOK_SECRET:
        return True  # secret not configured — skip verification (dev mode)
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")


# ---------------------------------------------------------------------------
# Task prompt builder
# ---------------------------------------------------------------------------

TASK_PROMPT_TEMPLATE = """\
{user_task}

When you are done with the implementation:
1. Run: git checkout -b {branch}
2. Run: git add -A && git commit -m "factory: {run_id}"
3. Run: gh pr create --title "{branch}" --body "Factory build {run_id}\\n\\nTask: {task_summary}" --base main
4. Update {heartbeat_file} with status: COMPLETED
"""


def _build_prompt(user_task: str, branch: str, run_id: str) -> str:
    task_summary = user_task[:200].replace('"', '\\"')
    return TASK_PROMPT_TEMPLATE.format(
        user_task=user_task,
        branch=branch,
        run_id=run_id,
        task_summary=task_summary,
        heartbeat_file=str(HEARTBEAT_FILE),
    )


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_claude(run_id: str, prompt: str) -> None:
    log_file = LOG_DIR / f"{run_id}.log"
    runs[run_id]["status"] = "running"
    runs[run_id]["started_at"] = time.time()

    _update_heartbeat(run_id, "RUNNING")

    log.info("Starting claude -p for run %s", run_id)

    try:
        with open(log_file, "w") as lf:
            result = subprocess.run(
                ["claude", "-p", prompt],
                stdout=lf,
                stderr=subprocess.STDOUT,
                cwd=str(FACTORY_ROOT),
                timeout=1800,  # 30-minute cap
            )
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        log.error("Run %s timed out", run_id)
        runs[run_id]["status"] = "timeout"
        _update_heartbeat(run_id, "TIMEOUT")
        return
    except Exception as exc:
        log.exception("Run %s failed with exception: %s", run_id, exc)
        runs[run_id]["status"] = "error"
        runs[run_id]["error"] = str(exc)
        _update_heartbeat(run_id, "ERROR")
        return

    if exit_code == 0:
        runs[run_id]["status"] = "completed"
        _update_heartbeat(run_id, "COMPLETED")
        log.info("Run %s completed successfully", run_id)
    else:
        runs[run_id]["status"] = "failed"
        runs[run_id]["exit_code"] = exit_code
        _update_heartbeat(run_id, "FAILED")
        log.warning("Run %s failed (exit %d)", run_id, exit_code)

    runs[run_id]["finished_at"] = time.time()


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
async def trigger(request: Request, background_tasks: BackgroundTasks):
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
    background_tasks.add_task(_run_claude, run_id, prompt)

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
