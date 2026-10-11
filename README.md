# the-factory

An autonomous software factory. Feature requests go in; verified, quality-gated PRs come out.

Built on **OpenHands** and **Claude Code**. Engineering discipline comes from **pstack**,
diffs are kept minimal by **Ponytail**, and **Thermo-Nuclear** reviews every PR.
Standalone: it shares no code or state with `the-machine`.

## Architecture

```
 ┌──────────┐   ┌────────────────┐   ┌──────────────────────┐   ┌──────────────┐   ┌────┐   ┌────────┐
 │  Intake  │──▶│    Planning    │──▶│        Build         │──▶│      QA      │──▶│ CI │──▶│ Deploy │
 │ Grok Bot │   │  /poteto-mode  │   │ OpenHands +          │   │thermo-nuclear│   │    │   │        │
 │          │   │  orchestrate   │   │ Claude Code+Ponytail │   │   review     │   │    │   │        │
 └──────────┘   └────────────────┘   └──────────────────────┘   └──────────────┘   └────┘   └────────┘
```

| Stage | Component | Responsibility |
|---|---|---|
| Intake | Signed webhook adapter (`factory/intake/`) | Take a task over HTTP and start a run. Grok Bot, the sender, is not built yet. |
| Planning | pstack `/poteto-mode` | Every build starts under `/poteto-mode`, which picks its own playbook. The `orchestrate` playbook for multi-PR work is not wired. |
| Build | OpenHands + Claude Code + Ponytail (`factory/build/`) | Claude Code runs in an OpenHands Docker sandbox with no GitHub credentials, one run at a time. The adapter publishes the PR. Ponytail keeps each diff to the minimum needed. |
| QA | Thermo-Nuclear, Ponytail review and tests (`factory/qa/`) | Run from main's copy of the workflow, so a PR cannot edit its own gate. A blocked PR goes back to a fresh builder up to twice, then to a human. |
| CI | GitHub Actions | pytest on every PR. No lint or type checks yet. |
| Deploy | TBD | Ship merged changes. |

## Ground rules

- Claude Code is the only build environment. No Cursor.
- Agents open PRs. They never push to the base branch.
- A PR merges only after it passes the QA gate. Branch protection requires `thermo-nuclear`, `ponytail-review` and `tests`.

See [`CLAUDE.md`](./CLAUDE.md) for the rules agents follow.

## Layout

```
.github/workflows/                                   QA gate and tests
.claude/skills/                                      pstack, Ponytail and the QA review skills
.claude/agents/                                      Claude Code subagents
factory/intake/                                      Signed webhook adapter, QA failure loop
factory/build/                                       OpenHands sandbox runner
factory/qa/                                          QA gate notes
tests/                                               Adapter and wiring tests
infra/cloudflare-tunnel/                             Public tunnel config (no credentials)
vendor/                                              pstack and Ponytail sources
```

## Status

Intake, Build and QA run end to end on one Mac under launchd. Grok Bot, Deploy, lint and type checks, and multi-PR planning are not built. Each `factory/*` README lists what is open.
