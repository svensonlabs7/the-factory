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
2. HMAC-SHA256 signature is verified against `FACTORY_WEBHOOK_SECRET`. The adapter refuses to start without it, because agents run with `--dangerously-skip-permissions`.
3. A `run_id` and `branch` name are generated.
4. `$CLAUDE_BIN -p --dangerously-skip-permissions "<task + git instructions>"` is spawned as a background subprocess.
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
export FACTORY_WEBHOOK_SECRET=$(openssl rand -hex 32)
uv run --with fastapi --with uvicorn -- uvicorn factory.intake.webhook_adapter:app --port 7654
```

Requests must carry an `X-Hub-Signature-256` header, or they get 401:

```bash
BODY='{"task": "Add a health-check endpoint to the intake service"}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$FACTORY_WEBHOOK_SECRET" | awk '{print $NF}')"
curl -X POST http://localhost:7654/trigger \
  -H "Content-Type: application/json" -H "X-Hub-Signature-256: $SIG" -d "$BODY"
```

## Running under launchd

`com.svenson.factory-intake.plist` runs the adapter on port 7654 and restarts it if it exits. Replace the `REPLACE_ME` values in the installed copy, never in this repo:

```bash
cp factory/intake/com.svenson.factory-intake.plist ~/Library/LaunchAgents/
chmod 600 ~/Library/LaunchAgents/com.svenson.factory-intake.plist
launchctl load ~/Library/LaunchAgents/com.svenson.factory-intake.plist
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `FACTORY_WEBHOOK_SECRET` | *(required)* | HMAC secret for signature verification |
| `CLAUDE_BIN` | `/Users/labs/.nvm/versions/node/v24.14.0/bin/claude` | Claude Code binary; launchd has no NVM on PATH |
| `GITHUB_TOKEN` | — | Token the agent's `gh pr create` uses |

## Prior art

`../../../grok-handoff/` uses the same pattern (GitHub issues → Claude Code → PR) as a LaunchDaemon watcher. This adapter is the HTTP-triggered equivalent.
