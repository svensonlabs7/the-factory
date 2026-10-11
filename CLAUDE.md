# The Factory — Autonomous Software Factory

## Purpose
An autonomous software factory: feature requests come in, reviewed PRs come out.
Built on OpenHands (build automation) + Claude Code (the agent doing the work).
Standalone — no code or state shared with `the-machine`.

## Hard Rules (NON-NEGOTIABLE)
- **Claude Code only. No Cursor.** pstack and the thermo-nuclear skill come from
  Cursor's plugin repo; use them through Claude Code, not Cursor.
- **Nothing merges without passing the QA gate** (`factory/qa/`).
- **PR-only.** Agents never push directly to a base branch.
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
- Full autonomous runs use `/poteto-mode` with the `autopilot-full` playbook (no human checkpoints until PR).
- Multi-PR / multi-day work goes through the `orchestrate` playbook.
- Core principles to apply without being asked: laziness-protocol (smallest change
  that solves it), prove-it-works (verify against the real artifact), fix-root-causes.
- Trivial edits (typos, one-line config) skip poteto-mode.

## Cursor-only references in pstack
pstack was written for Cursor. Read its Cursor-only terms this way in Claude Code and in factory runs.

| pstack says | Do this |
|---|---|
| `cursor-team-kit` plugin | Not installed. Use the rows below for its skills. |
| `deslop` | Run `/simplify` if available, then pstack's `/unslop` on prose. |
| `control-cli`, `control-ui` | Drive the real CLI with Bash. For a UI, use browser tools if present. Otherwise say what was not verified. |
| `create-skill` | Write the SKILL.md by hand, following `playbooks/authoring-a-skill.md`. |
| Bugbot | None here. The QA gate (thermo-nuclear, ponytail-review, tests) takes its place. Skip Bugbot triage steps. |
| `grok-*` models, cloud agent | Claude subagents. Use `opus` for hard changes and judgment, `sonnet` for routine code. |
| `generalPurpose`, `Task` | The `Agent` tool with `subagent_type: "poteto-agent"`. |
| Origin (`origin pr`), Graphite (`gt`) | Use `gh`. pstack already falls back to it. Never require Graphite. |
| `AskQuestion` | Factory runs have no human. Decide, act and report, as poteto-mode's "never block on the human" says. |
| `~/.cursor`, `.cursor/`, `.mdc`, `alwaysApply`, `/setup-pstack` | Skip. Cursor rules files do nothing in Claude Code. |
| `/loop`, Plan Mode | Skip in factory runs, which are one pass. Interactive sessions can use Claude Code's own `/loop` and plan mode. |
| Pushing and opening a PR | Factory runs never do either. The adapter publishes the committed branch. Skip those playbook steps. |

## Generation: Ponytail
- Ponytail enforces minimum code at generation time. Its rules are the vendored skill
  `.claude/skills/ponytail/SKILL.md`, because factory sandboxes install no plugins.
  Developers also get the `ponytail@ponytail` plugin from `.claude/settings.json`. Generated diffs should be the
  smallest change that satisfies the request. No speculative abstractions, no
  unrequested features, no compatibility shims.

## QA Gate: Thermo-Nuclear
- Skill: `.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`
- Runs on every PR before merge, from main's copy of the workflow, next to `ponytail-review` and `tests`. All three are required checks. It is user-invoked only
  (`disable-model-invocation: true`), so the QA pipeline invokes it explicitly:
  `/thermo-nuclear-code-quality-review`.
- Presumptive blockers: a file pushed past 1000 lines, ad-hoc branching in existing
  flows, unnecessary wrappers/casts, logic in the wrong layer, duplicated helpers.

## Intake: Grok Bot
- Grok Bot is the intake layer for feature requests once the factory is running.
- Agents do not take work from anywhere else without explicit operator approval.

## Health: HEARTBEAT.md
`HEARTBEAT.md` tracks pipeline status (last run, QA gate result, open incidents).
Updated in place by the intake adapter as each run progresses; polled by `the-machine` for cross-system health.

## Pipeline
Intake (Grok Bot) → Planning (`/poteto-mode` orchestrate) → Build (OpenHands +
Claude Code + Ponytail) → QA (thermo-nuclear) → CI → Deploy

## Layout
- `factory/intake/` — signed webhook adapter and QA failure loop
- `factory/build/` — OpenHands sandbox runner
- `factory/qa/` — QA gate notes (the gate itself is `.github/workflows/qa-gate.yml`)
- `tests/` — adapter and wiring tests
- `vendor/` — pstack and Ponytail sources
- `.claude/skills/`, `.claude/agents/` — Claude Code skills and subagents
