# THE-FACTORY

Autonomous software factory. Separate repo from the-machine.
Built on OpenHands + pstack + Ponytail 5 + Thermo-Nuclear QA.

## Entry Point

Always start with `/poteto-mode` (pstack). This activates the full
engineering stack: 22 playbooks, 21 principles, structured planning,
Grok/Sonnet/Fable/Opus 5 model panel.

## Core Skills

| Skill | Purpose |
|---|---|
| `/poteto-mode` | Main engineering mode |
| `/orchestrate` | Multi-day, multi-PR feature fleets |
| `/autopilot-full` | PRs planned → built → merged autonomously |
| `/swarm` | Parallel worker spawning |
| `/make-bot-ui` | Grok Bot webhook intake UI |
| `/arena` | Competing implementation options |
| `/interrogate` | Deep codebase understanding |

## Plugins Required

```bash
# Install after opening this project in Claude Code:
/add-plugin pstack
/plugin marketplace add DietrichGebert/ponytail
```

## QA Gate

`.claude/skills/thermo-nuclear-code-quality-review/SKILL.md` is the
gate. Runs before any PR merges. Blocks structural regressions.

Philosophy: **code judo** — restructurings that delete whole layers.

## Laws

1. No file > 1000 lines. If you're near it, split.
2. No ad-hoc conditionals. Every branch should map to a real abstraction.
3. Ponytail enforces minimum code at generation time. Lean by default.
4. 98% of risky logic ships with a test (Ponytail 5 guarantee).
5. Claude Code only. No Cursor.

## Pipeline

```
Grok Bot intake
    ↓
/orchestrate (pstack) — planning, PRD, task breakdown
    ↓
OpenHands + Claude Code + Ponytail — build lean
    ↓
Thermo-Nuclear QA gate — blocks structural regressions
    ↓
CI
    ↓
deploy
    ↓
HEARTBEAT.md → the-machine (monitoring)
```

## Heartbeat

The factory reports its last run, active jobs, and any QA failures to
`HEARTBEAT.md`. The-machine's monitoring picks this up.

## Environment

- Runtime: Mac Mini M4 (the-machine)
- Orchestration: OpenClaw v2026.4.5
- Model: Fable / Sonnet 4.6 / Opus 5 (pstack panel)
