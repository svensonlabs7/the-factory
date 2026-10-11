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
7. The adapter fetches the branch into the main checkout, pushes it and opens the PR with `gh`. It runs git only in the main checkout, because git run in the agent's clone would execute hooks and config the agent wrote there. The one touch is a fetch that reads objects from the clone.
8. The run waits for the required checks on the PR (status `qa`). If they all pass, it is `completed`.
9. If a check fails, a fresh builder in a new container gets the reviewers' findings and the branch, and pushes a fix. This repeats up to twice. If the PR is still blocked, the run is `blocked` and HEARTBEAT.md says why.
10. `HEARTBEAT.md`'s status table is updated at each stage, and logs land in `.factory-logs/<run_id>.log`, one section per attempt.

## QA failure loop

The adapter asks `gh pr checks --required`, so it never carries its own list of checks. It first waits for the PR to reach the commit it pushed, because GitHub briefly keeps showing the previous commit's results. "No checks reported yet" means keep waiting, and any other `gh` error ends the run. The gate keeps each reviewer's text as a `review-<check>` artifact, and a failed `tests` run contributes its log tail. The findings go into the next builder's prompt as data, with dashes defanged so they cannot forge the end of their fence. A fix round that makes no commits, or that leaves the branch with no net changes against main, is an error: deleting the work is not a way to pass. Runs go one at a time, so a PR waiting on the gate holds the queue.

## Task prompt

The prompt starts with `/poteto-mode`, so pstack picks a playbook. It then appends:

```
Follow the ponytail skill: the smallest change that fully solves the task.
You are in a git repository on branch factory/<run_id>. When you are done, run: git add -A && git commit -m "factory: <run_id>"
Do not push or open a PR, and skip any playbook step that does. The factory publishes your branch.
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
| `FACTORY_AGENT_CMD` | `uv run -q --script factory/build/run_agent.py` | Command that runs the agent. Called as `<command> <workdir> <prompt> <timeout-seconds>` |
| `GH_BIN` | `gh` | Used on the host to open the PR. Tests replace it |

## Prior art

`../../../grok-handoff/` uses the same pattern (GitHub issues → Claude Code → PR) as a LaunchDaemon watcher. This adapter is the HTTP-triggered equivalent.
