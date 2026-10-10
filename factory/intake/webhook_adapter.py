"""
the-factory: Grok Bot → Claude Code webhook adapter.

Uses `claude -p` (Claude Code headless) with your Pro subscription.
No API key needed — authenticates via existing Claude login.

Run:
    cd /Users/labs/projects/the-factory
    uv run --with fastapi --with uvicorn -- uvicorn factory.intake.webhook_adapter:app --host 0.0.0.0 --port 7654

Or add __init__.py files (see README) and run directly.
"""

import hashlib
import hmac as hmac_module
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="the-factory intake", version="2.0.0")

# Config from environment
WEBHOOK_SECRET = os.environ.get("FACTORY_WEBHOOK_SECRET", "")
FACTORY_REPO = os.environ.get("FACTORY_REPO", "/Users/labs/projects/the-factory")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOG_DIR = Path(FACTORY_REPO) / ".factory-logs"


def verify_signature(body: bytes, signature_header: str) -> bool:
    """Verify HMAC-SHA256 signature from Grok Bot."""
    if not WEBHOOK_SECRET:
        return True  # dev mode — no secret configured
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    mac = hmac_module.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac_module.compare_digest(expected, signature_header)


def build_claude_task(user_task: str, run_id: str, branch: str) -> str:
    """Build the full task prompt for claude -p, including git/PR instructions."""
    return f"""{user_task}

When your implementation is complete, do the following git steps in order:
1. git checkout -b {branch}
2. git add -A
3. git commit -m "factory({run_id}): {user_task[:60].strip()}"
4. gh pr create --title "{branch}" --body "Factory build {run_id}\\n\\nTask: {user_task[:300]}" --base main

Then update the file /Users/labs/projects/the-factory/HEARTBEAT.md:
- Set FACTORY STATUS to COMPLETED
- Set Last run to the current timestamp
- Set the completed run ID to {run_id}
"""


def spawn_claude(run_id: str, task: str, branch: str) -> subprocess.Popen:
    """Spawn claude -p as a background process. Uses Pro subscription, no API key."""
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{run_id}.log"

    full_task = build_claude_task(task, run_id, branch)

    env = os.environ.copy()
    if GITHUB_TOKEN:
        env["GITHUB_TOKEN"] = GITHUB_TOKEN
    env["FACTORY_RUN_ID"] = run_id

    cmd = ["/Users/labs/.nvm/versions/node/v24.14.0/bin/claude", "-p", "--dangerously-skip-permissions", full_task]

    with open(log_file, "w") as f:
        proc = subprocess.Popen(
            cmd,
            cwd=FACTORY_REPO,
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
        )

    meta = {
        "run_id": run_id,
        "task": task,
        "branch": branch,
        "pid": proc.pid,
        "started_at": datetime.utcnow().isoformat(),
        "status": "running",
        "log": str(log_file),
        "agent": "claude -p (Pro subscription)",
    }
    (LOG_DIR / f"{run_id}.meta.json").write_text(json.dumps(meta, indent=2))

    return proc


def update_heartbeat(run_id: str, task: str):
    """Update HEARTBEAT.md with current run info."""
    heartbeat_path = Path(FACTORY_REPO) / "HEARTBEAT.md"
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    content = heartbeat_path.read_text() if heartbeat_path.exists() else ""

    new_block = f"\n\n---\n**BUILDING** | Run: `{run_id}` | Started: {now}\nTask: {task[:120]}\n"
    heartbeat_path.write_text(content + new_block)


@app.post("/trigger")
async def trigger(request: Request):
    """
    Grok Bot sends a feature request here to kick off a factory run.

    Body:
        {
            "task": "Add dark mode toggle. Create a PR when done.",
            "branch": "feat/dark-mode",     # optional
            "run_id": "grok-20261010-..."   # optional
        }

    Header:
        X-Grok-Signature: sha256=<HMAC-SHA256 of body>
    """
    body = await request.body()

    if not verify_signature(body, request.headers.get("X-Grok-Signature", "")):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    task = payload.get("task", "").strip()
    if not task:
        raise HTTPException(status_code=400, detail="'task' is required")

    run_id = payload.get("run_id") or f"factory-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    branch = payload.get("branch") or f"factory/{run_id}"

    update_heartbeat(run_id, task)
    proc = spawn_claude(run_id, task, branch)

    return JSONResponse({
        "status": "accepted",
        "run_id": run_id,
        "pid": proc.pid,
        "branch": branch,
        "agent": "claude -p",
        "log": str(LOG_DIR / f"{run_id}.log"),
    })


@app.get("/status/{run_id}")
async def status(run_id: str):
    meta_path = LOG_DIR / f"{run_id}.meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    meta = json.loads(meta_path.read_text())
    try:
        os.kill(meta["pid"], 0)
        meta["status"] = "running"
    except (ProcessLookupError, KeyError):
        meta["status"] = "completed"
    return JSONResponse(meta)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "factory": FACTORY_REPO,
        "agent": "claude -p (Pro subscription)",
        "time": datetime.utcnow().isoformat(),
    }
