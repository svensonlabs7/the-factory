# pstack in Claude Code

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
| `/no-comments` (Comment Sicko) before review | Skip. Comments follow the ponytail skill: only the why the code cannot show, matching the surrounding code. |
