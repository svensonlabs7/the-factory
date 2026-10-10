# the-factory

> Autonomous software factory. Separate from the-machine.

## What Is This

the-factory is a self-contained software engineering system designed to receive
feature requests via Grok Bot, plan and build them autonomously using OpenHands
and Claude Code, enforce lean code via Ponytail 5, gate quality via the
Thermo-Nuclear skill, and deploy — all without a human in the loop.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   INTAKE                            │
│  Grok Bot webhook → structured feature brief        │
└───────────────────────┬──────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│                   PLANNING                          │
│  pstack /poteto-mode + /orchestrate                 │
│  → PRD + task breakdown + PR fleet                  │
└───────────────────────┬──────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│                   BUILD                             │
│  OpenHands Automation Server                        │
│  Claude Code backend + Ponytail 5 (lean by default) │
│  53% less code · 41% faster · 26% cheaper          │
└───────────────────────┬──────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│                   QA GATE                           │
│  Thermo-Nuclear Code Quality Review                 │
│  Blocks: files >1k lines, ad-hoc conditionals,      │
│  structural regressions, missing tests on risky logic│
└───────────────────────┬──────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│                   CI + DEPLOY                       │
│  /autopilot-full — PRs → merged → deployed          │
└───────────────────────┬──────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│                   MONITOR                           │
│  HEARTBEAT.md → the-machine dashboard               │
└──────────────────────────────────────────────────────┘
```

## Setup

1. Open this repo in Claude Code
2. Install plugins:
   ```
   /add-plugin pstack
   /plugin marketplace add DietrichGebert/ponytail
   ```
3. Start with `/poteto-mode` to activate the full engineering stack

## Directory Structure

```
the-factory/
├── .claude/
│   └── skills/
│       └── thermo-nuclear-code-quality-review/
│           └── SKILL.md          ← QA gate definition
├── factory/
│   ├── intake/                   ← Grok Bot intake pipeline
│   ├── build/                    ← OpenHands build automation
│   └── qa/                       ← QA gate scripts + config
├── vendor/
│   └── pstack/
│       └── README.md             ← pstack reference
├── CLAUDE.md                     ← factory rules
├── HEARTBEAT.md                  ← status → the-machine
└── README.md
```

## Philosophy

**Code judo.** The best code review restructures things to delete whole layers.
Less code = less surface area = fewer bugs. Ponytail enforces this at generation
time. Thermo-nuclear enforces it at review time.

## Related

- the-machine: `/Users/labs/projects/the-machine` — monitoring + dashboards
- pstack: https://github.com/cursor/plugins/tree/main/pstack
- OpenHands: https://github.com/All-Hands-AI/OpenHands
- Ponytail: https://github.com/DietrichGebert/ponytail
