# Build — OpenHands + Claude Code + Ponytail

**Status: sandbox wired** (`run_agent.py`)

Takes planned work units and produces PRs. OpenHands provides sandboxed, automated
agent runs, Claude Code does the engineering under `/poteto-mode`, and Ponytail keeps
each generated diff to the minimum needed.

`run_agent.py` starts the OpenHands agent-server image (pinned by digest, arm64) in Docker and runs
Claude Code in it through the SDK's `ACPAgent`. The sandbox mounts one clone and holds no GitHub
credentials. `CLAUDE_CODE_OAUTH_TOKEN` reaches it as a container environment variable, because the
SDK masks `acp_env` when it sends it to the server. The Docker VM mounts only the home directory,
so run directories live under it. SDK and image versions must match: 1.54.0, set at the top of `run_agent.py`.

## To decide

- [x] OpenHands deployment: local Docker on this host
- [x] How OpenHands drives Claude Code: `ACPAgent` with `claude-agent-acp`, tokens from the Claude plan
- [ ] Ponytail integration point: prompt, hook, or post-generation check
- [ ] Sandbox and permission scope per task (allowed tools, budget cap, retries)
- [ ] Branch/PR conventions: one PR per work unit, stacked where needed
- [ ] Hand-off to QA (`../qa/`)
