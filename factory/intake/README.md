# Intake — Webhook Adapter

Receives task payloads via HTTP and spawns **Claude Code** (`claude -p`) in headless mode to execute them. Uses your existing Claude Pro subscription — no API key required.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/trigger` | Queue a new factory run |
| `GET` | `/status/:run_id` | Poll run state |
| `GET` | `/health` | Liveness check |

## How it works

1. A webhook POST arrives at `/trigger` with a `task` string.
2. HMAC-SHA256 signature is verified against `FACTORY_WEBHOOK_SECRET` (skipped in dev if unset).
3. A `run_id` and `branch` name are generated.
4. `claude -p "<task + git instructions>"` is spawned as a background subprocess.
5. Claude Code implements the task, creates a branch, commits, and opens a PR via `gh pr create`.
6. `HEARTBEAT.md` is updated with the run status.
7. Logs land in `.factory-logs/<run_id>.log`.

## Task prompt

The prompt sent to `claude -p` automatically appends:

```
1. git checkout -b factory/<run_id>
2. git add -A && git commit -m "factory: <run_id>"
3. gh pr create --title "factory/<run_id>" --body "..." --base main
4. Update HEARTBEAT.md with status: COMPLETED
```

## Running locally

```bash
pip install fastapi uvicorn
uvicorn factory.intake.webhook_adapter:app --reload --port 8080
```

```bash
curl -X POST http://localhost:8080/trigger \
  -H "Content-Type: application/json" \
  -d '{"task": "Add a health-check endpoint to the intake service"}'
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `FACTORY_WEBHOOK_SECRET` | *(empty — dev mode)* | HMAC secret for signature verification |

## Prior art

`../../../grok-handoff/` uses the same pattern (GitHub issues → Claude Code → PR) as a LaunchDaemon watcher. This adapter is the HTTP-triggered equivalent.
