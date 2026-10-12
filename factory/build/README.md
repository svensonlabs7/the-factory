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

## Network lock-down

The sandbox holds the Claude token, so it must not reach arbitrary hosts. Before every run, `egress.sh`:

1. Creates the `factory-sandbox` Docker network (172.30.0.0/24) if missing.
2. Runs `factory-egress`, a tinyproxy container at 172.30.0.2, that tunnels only to the hosts in `egress/allow`
   (Claude's API and the npm and PyPI registries). It is recreated only when its config changes.
3. Adds a `FACTORY-EGRESS` chain to the Colima VM's `DOCKER-USER` firewall chain: only the proxy may leave the
   subnet, everything else from it is dropped. Re-applied every run, because Colima loses it on restart.
4. Proves it: a direct connection from the sandbox network must fail, and the proxy must pass `api.anthropic.com`.
   If either check fails, the script exits non-zero and the run does not start.

`run_agent.py` then starts the container on that network with `HTTPS_PROXY` set inside it.

Known limits: DNS lookups still go through Docker's resolver, a low-bandwidth channel out. And an allowed registry
accepts uploads as well as downloads, so a determined agent with its own registry account could publish data there.
Remove the registries from `egress/allow` if a project needs no dependencies.

## To decide

- [x] OpenHands deployment: local Docker on this host
- [x] How OpenHands drives Claude Code: `ACPAgent` with `claude-agent-acp`, tokens from the Claude plan
- [ ] Ponytail integration point: prompt, hook, or post-generation check
- [ ] Sandbox and permission scope per task (allowed tools, budget cap, retries). Network: locked down (see above).
- [ ] Branch/PR conventions: one PR per work unit, stacked where needed
- [ ] Hand-off to QA (`../qa/`)
