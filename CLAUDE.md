# The Factory — Autonomous Software Factory

## Purpose
An autonomous software factory: feature requests come in, reviewed PRs come out.
Built on OpenHands (build automation) + Claude Code (the agent doing the work).
Standalone — no code or state shared with `the-machine`.

## Hard Rules (NON-NEGOTIABLE)
- **Claude Code only. No Cursor.** pstack and the thermo-nuclear skill come from
  Cursor's plugin repo; use them through Claude Code, not Cursor.
- **Nothing merges without passing the QA gate** (`factory/qa/`).
- Agents may push directly to any branch, including `main`.
- Secrets live in `.env` (never committed).

## Engineering Mode: pstack / poteto-mode
- pstack is the default engineering mode. Reference: `vendor/pstack/README.md`.
  Its skills and agents are vendored into `.claude/skills/` and `.claude/agents/`
  (source commit in `vendor/pstack/SOURCE`). It is not a Claude Code plugin.
- pstack's model routing names Cursor models (grok-*, opus-5). In Claude Code, route
  every role to Claude subagents (`opus` for judgment and hard changes, `sonnet` for
  routine code). Skip `/setup-pstack`; it writes Cursor rules.
- Use `/poteto-mode` for every non-trivial task. It picks a playbook (bug fix,
  feature, refactoring, orchestrate, ...) and runs the supporting skills.
- Full autonomous runs use `/autopilot-full` (no human checkpoints until PR).
- Multi-PR / multi-day work goes through the `orchestrate` playbook.
- Core principles to apply without being asked: laziness-protocol (smallest change
  that solves it), prove-it-works (verify against the real artifact), fix-root-causes.
- Trivial edits (typos, one-line config) skip poteto-mode.

## Generation: Ponytail
- Ponytail (`ponytail@ponytail` plugin, project scope in `.claude/settings.json`)
  enforces minimum code at generation time. Generated diffs should be the
  smallest change that satisfies the request. No speculative abstractions, no
  unrequested features, no compatibility shims.

## QA Gate: Thermo-Nuclear
- Skill: `.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`
- Runs on every PR before merge. It is user-invoked only
  (`disable-model-invocation: true`), so the QA pipeline invokes it explicitly:
  `/thermo-nuclear-code-quality-review`.
- Presumptive blockers: a file pushed past 1000 lines, ad-hoc branching in existing
  flows, unnecessary wrappers/casts, logic in the wrong layer, duplicated helpers.

## Intake: Grok Bot
- Grok Bot is the intake layer for feature requests once the factory is running.
- Agents do not take work from anywhere else without explicit operator approval.

## Health: HEARTBEAT.md
`HEARTBEAT.md` tracks pipeline status (last run, QA gate result, open incidents).
Updated by the QA agent after each run; polled by `the-machine` for cross-system health.

## Pipeline
Intake (Grok Bot) → Planning (`/poteto-mode` orchestrate) → Build (OpenHands +
Claude Code + Ponytail) → QA (thermo-nuclear) → CI → Deploy

## Layout
- `factory/intake/` — Grok Bot feature-request pipeline
- `factory/build/` — OpenHands build automation
- `factory/qa/` — thermo-nuclear + Ponytail QA gate
- `vendor/pstack/` — pstack reference
- `.claude/skills/`, `.claude/agents/` — Claude Code skills and subagents
