# The Factory

Feature requests come in through a signed webhook. The factory builds each one in an OpenHands sandbox with Claude
Code, and opens a PR that the QA gate reviews. It shares no code or state with `the-machine`.

## Hard rules
- Claude Code only, no Cursor.
- PR-only: agents never push to a base branch. Nothing merges without the required checks: thermo-nuclear,
  ponytail-review, ux-laws, tests, lint and secrets.
- Secrets live in `.env`, which is never committed.
- Work comes only from the webhook (Grok Bot) or the operator.

## How to work
- Non-trivial tasks use `/poteto-mode`. Full autonomous runs use its `autopilot-full` playbook, and trivial edits skip it.
- Before running a pstack skill, read `vendor/pstack/CLAUDE-CODE.md`, which maps the Cursor-only steps it names.
- Make the smallest change that solves the task (the ponytail skill).
- For UI changes, run the ux-laws skill before and after building.

## Gotchas
- The gate runs main's copy of `.github/workflows/qa-gate.yml` and its skills (`pull_request_target`). A PR's edits to
  them take effect only after it merges.
- The adapter runs from this folder and loads whatever branch is checked out when it restarts. Keep `main` checked
  out, restart with `factory/intake/restart.sh`, and check that `/health` shows the new `commit`.
- `HEARTBEAT.md` is untracked and rewritten every minute. To change its shape, edit `HEARTBEAT.template.md`.
- Run the tests with `uv run --locked --group test python -m pytest -q`. A plain `uv run pytest` cannot import `factory`.
