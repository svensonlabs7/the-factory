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
2. The request must be signed, fresh and new: an HMAC-SHA256 over `<timestamp>.<body>` under `FACTORY_WEBHOOK_SECRET`, a timestamp within 5 minutes, and a signature not seen before. A replay returns 401, and the replay memory survives a restart. The adapter refuses to start without it, because agents run with permission prompts off.
3. A `run_id` and `branch` name are generated (a requested branch must start with `factory/`), and the run waits its turn. Runs go one at a time.
4. The adapter clones the repo into `../the-factory-runs/<run_id>` and checks out the branch.
5. `factory/build/run_agent.py` starts a Docker container from the pinned OpenHands agent-server image. It mounts only that clone and runs Claude Code in it. The container holds no GitHub credentials.
6. The agent implements the task and commits.
7. The adapter fetches the branch into the main checkout, pushes it and opens the PR with `gh`. It runs git only in the main checkout, because git run in the agent's clone would execute hooks and config the agent wrote there. The one touch is a fetch that reads objects from the clone.
8. The run waits for the required checks on the PR (status `qa`). If they all pass, it is `completed`.
9. If a check fails, a fresh builder in a new container gets the reviewers' findings and the branch, and pushes a fix. This repeats up to twice. If the PR is still blocked, the run is `blocked` and HEARTBEAT.md says why.
10. `HEARTBEAT.md`'s status table is updated at each stage, and logs land in `.factory-logs/<run_id>.log`, one section per attempt.

## Rejected requests

Every `/trigger` request refused with a 401, 422 or 429 appends one JSON line to `.factory-logs/rejected.jsonl`: time, a fixed reason, the caller's IP (`CF-Connecting-IP`, else the socket), path and the first 100 characters of the user agent. The body, the signature and the timestamp header are deliberately never logged, and neither is the pydantic error text of a 422, since it echoes the input. The file stops growing at 5 MB. Capacity refusals (429) are logged but are not counted as an attack. When 20 or more 401 or 422 rejections fall in the last hour, `open_incidents` in `HEARTBEAT.md` reads "N rejected requests in the last hour" (N as of the moment it opened). It is written only when the flag flips and returns to "none" on the first rejection after the burst has aged out. The count lives in memory, so a restart resets it.

## Run state

Each run's state is one file, `.factory-logs/<run_id>.meta.json`, and `/status/<run_id>` serves that file, so it survives a restart. A restart kills the worker, so on startup any run still `queued`, `running` or `qa` is closed out as `error` ("the service restarted during the run"), and HEARTBEAT.md follows. The PR it opened, if any, stays open and is listed as `last_pr_blocked`.

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

Requests must carry `X-Factory-Timestamp` (Unix seconds) and `X-Hub-Signature-256` (the HMAC of `<timestamp>.<body>`), or they get 401. Sending the same signed request twice also gets 401:

```bash
BODY='{"task": "Add a health-check endpoint to the intake service"}'
TS=$(date +%s)
SIG="sha256=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$FACTORY_WEBHOOK_SECRET" | awk '{print $NF}')"
curl -X POST http://localhost:7654/trigger \
  -H "Content-Type: application/json" -H "X-Factory-Timestamp: $TS" -H "X-Hub-Signature-256: $SIG" -d "$BODY"
```

## Running under launchd

`com.svenson.factory-intake.plist` runs the adapter on port 7654, listening on `127.0.0.1` only, and restarts it if it exits. An external sender such as Grok Bot reaches it through a tunnel that forwards to localhost. It reads secrets from the repo's `.env`:

```bash
echo "FACTORY_WEBHOOK_SECRET=$(openssl rand -hex 32)" >> .env
mkdir -p .factory-logs  # launchd opens its log files before the adapter can create this
cp factory/intake/com.svenson.factory-intake.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.svenson.factory-intake.plist
```

## Rotating the webhook secret

While `FACTORY_WEBHOOK_SECRET_PREVIOUS` is set, a request signed with either secret is accepted. An empty value counts as unset.

1. Generate a new secret: `openssl rand -hex 32`.
2. In `.env`, set `FACTORY_WEBHOOK_SECRET_PREVIOUS` to the old `FACTORY_WEBHOOK_SECRET` value and `FACTORY_WEBHOOK_SECRET` to the new one. The file must end in a newline before you append, or the last line is corrupted.
3. Restart the agent: `launchctl kickstart -k gui/$(id -u)/com.svenson.factory-intake`.
4. Switch the sender (Grok Bot) to the new secret.
5. Once the sender uses only the new secret, delete `FACTORY_WEBHOOK_SECRET_PREVIOUS` from `.env` and restart again.

The old secret stays valid for as long as `FACTORY_WEBHOOK_SECRET_PREVIOUS` is set, so remove it promptly.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `FACTORY_WEBHOOK_SECRET` | *(required)* | HMAC secret for signature verification |
| `FACTORY_WEBHOOK_SECRET_PREVIOUS` | *(unset)* | Old secret still accepted during a rotation. Empty means none |
| `FACTORY_ROOT` | `/Users/labs/projects/the-factory` | Checkout the service runs from. Tests point it at a temporary repo |
| `CLAUDE_CODE_OAUTH_TOKEN` | *(required for real runs)* | Pro plan token from `claude setup-token`. Forwarded into the sandbox |
| `FACTORY_AGENT_CMD` | `uv run -q --script factory/build/run_agent.py` | Command that runs the agent. Called as `<command> <workdir> <prompt> <timeout-seconds>` |
| `GH_BIN` | `gh` | Used on the host to open the PR. Tests replace it |

## Prior art

`../../../grok-handoff/` uses the same pattern (GitHub issues → Claude Code → PR) as a LaunchDaemon watcher. This adapter is the HTTP-triggered equivalent.
