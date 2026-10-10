# Build — OpenHands + Claude Code + Ponytail

**Status: stub**

Takes planned work units and produces PRs. OpenHands provides sandboxed, automated
agent runs, Claude Code does the engineering under `/poteto-mode`, and Ponytail keeps
each generated diff to the minimum needed.

## To decide

- [ ] OpenHands deployment: local Docker on this host, or remote runtime
- [ ] How OpenHands drives Claude Code (agent/LLM config, headless `claude -p`)
- [ ] Ponytail integration point: prompt, hook, or post-generation check
- [ ] Sandbox and permission scope per task (allowed tools, budget cap, retries)
- [ ] Branch/PR conventions: one PR per work unit, stacked where needed
- [ ] Hand-off to QA (`../qa/`)
