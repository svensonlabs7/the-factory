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
| Intake | Grok Bot (`factory/intake/`) | Take feature requests and turn them into structured work items. |
| Planning | pstack `/poteto-mode` → `orchestrate` playbook | Split work into stacked, verifiable PRs and assign agents. |
| Build | OpenHands + Claude Code + Ponytail (`factory/build/`) | Run agents in sandboxes. Ponytail keeps each diff to the minimum needed. |
| QA | Thermo-Nuclear (`factory/qa/`) | Strict maintainability review. Blocking findings send the PR back to Build. |
| CI | GitHub Actions (TBD) | Tests, lint, and type checks. |
| Deploy | TBD | Ship merged changes. |

## Ground rules

- Claude Code is the only build environment. No Cursor.
- Agents open PRs. They never push to the base branch.
- A PR merges only after it passes the QA gate.

See [`CLAUDE.md`](./CLAUDE.md) for the rules agents follow.

## Layout

```
.claude/skills/thermo-nuclear-code-quality-review/   QA review skill
.claude/agents/                                      Claude Code subagents
factory/intake/                                      Grok Bot intake pipeline
factory/build/                                       OpenHands build automation
factory/qa/                                          QA gate
vendor/pstack/                                       pstack reference
```

## Status

Scaffold only. Each `factory/*` directory has a stub README with the open design questions.
