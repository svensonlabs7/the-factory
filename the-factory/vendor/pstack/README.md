# pstack — poteto's Engineering Stack

Source: https://github.com/cursor/plugins/tree/main/pstack
Author: poteto (React core team, ex-Meta/Netflix/Cursor)

## Install

In Claude Code:
```
/add-plugin pstack
```

## Entry Point

```
/poteto-mode
```

Activates the full engineering stack. Always start here for any
non-trivial task in the-factory.

## Key Commands

| Command | Purpose |
|---|---|
| `/poteto-mode` | Main engineering mode — activates all playbooks |
| `/orchestrate` | Multi-day, multi-PR feature fleet planning |
| `/autopilot-full` | Autonomous PRs: planned → built → merged |
| `/swarm` | Parallel worker spawning for independent tasks |
| `/make-bot-ui` | Builds Grok Bot webhook intake UI |
| `/arena` | Competing implementation options side-by-side |
| `/interrogate` | Deep codebase understanding before touching code |

## Model Panel

Default models configured in pstack:
- Fable (fast/cheap)
- Sonnet 4.6 (balanced)
- Grok (external perspective)
- Opus 5 (deep reasoning)

## Subagent Type

pstack exposes a `poteto-agent` subagent type for spawning rigorous
sub-agents on isolated tasks. Use via the Agent tool with
`subagent_type: "poteto-agent"`.

## Philosophy

22 engineering playbooks + 21 principles baked into every task.
Opinionated, structured, fast.
