# Intake — Webhook Adapter

Receives task payloads via HTTP and runs **Claude Code** on them inside an OpenHands Docker sandbox. Uses your Claude Pro subscription through `CLAUDE_CODE_OAUTH_TOKEN`, with no API key.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/trigger` | Queue a new factory run |
| `GET` | `/status/:run_id` | Poll run state |
| `GET` | `/health` | Liveness check |

## How it works

1. A webhook POST arrives at `/trigger` with a `task` string.
2. HMAC-SHA256 signature is verified against `FACTORY_WEBHOOK_SECRET`. The adapter refuses to start without it, because agents run with permission prompts off.
3. A `run_id` and `branch` name are generated, and the run waits its turn. Runs go one at a time.
4. The adapter clones the repo into `../the-factory-runs/<run_id>` and checks out the branch.
5. `factory/build/run_agent.py` starts a Docker container from the pinned OpenHands agent-server image. It mounts only that clone and runs Claude Code in it. The container holds no GitHub credentials.
6. The agent implements the task and commits.
7. The adapter fetches the branch into the main checkout, pushes it and opens the PR with `gh`. It never runs git inside the agent's clone, because git would execute hooks and config the agent wrote there.
8. `HEARTBEAT.md` is updated with the run status, and logs land in `.factory-logs/<run_id>.log`.

## Task prompt

The prompt sent to the agent automatically appends:

```
You are in a git repository on branch factory/<run_id>. When you are done, run: git add -A && git commit -m "factory: <run_id>"
Do not push. The factory publishes your branch.
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

`com.svenson.factory-intake.plist` runs the adapter on port 7654, listening on all interfaces (`0.0.0.0`) so external webhooks can reach it, and restarts it if it exits. It reads secrets from the repo's `.env`:

```bash
echo "FACTORY_WEBHOOK_SECRET=$(openssl rand -hex 32)" >> .env
mkdir -p .factory-logs  # launchd opens its log files before the adapter can create this
cp factory/intake/com.svenson.factory-intake.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.svenson.factory-intake.plist
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `FACTORY_WEBHOOK_SECRET` | *(required)* | HMAC secret for signature verification |
| `CLAUDE_CODE_OAUTH_TOKEN` | *(required for real runs)* | Pro plan token from `claude setup-token`. Forwarded into the sandbox |
| `FACTORY_AGENT_CMD` | `uv run … python factory/build/run_agent.py` | Command that runs the agent. Called as `<command> <workdir> <prompt>` |
| `GH_BIN` | `gh` | Used on the host to open the PR. Tests replace it |

## Prior art

`../../../grok-handoff/` uses the same pattern (GitHub issues → Claude Code → PR) as a LaunchDaemon watcher. This adapter is the HTTP-triggered equivalent.
