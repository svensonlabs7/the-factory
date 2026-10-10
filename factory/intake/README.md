# Intake — Grok Bot

**Status: stub**

Grok Bot is how feature requests enter the factory. Intake turns each request into a
structured work item for the Planning stage.

## Prior art

`../../../grok-handoff/` (sibling project) already runs a Grok → Claude Code handoff:
- GitHub issues labeled `agent-handoff` act as the queue
- A LaunchDaemon watcher polls the issues and runs Claude Code in an isolated worktree
- The wrapper does the commit, push, and PR itself; nothing merges automatically

Reuse that approach or migrate it here rather than building a second queue.

## To decide

- [ ] Queue: GitHub issues (as in grok-handoff) or something else
- [ ] Work-item schema: title, problem, acceptance criteria, target repo, priority
- [ ] Hand-off to Planning (`/poteto-mode` orchestrate)
- [ ] Rejecting or clarifying underspecified requests
- [ ] Auth: what Grok Bot is allowed to create or trigger
