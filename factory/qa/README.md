# QA Gate — Thermo-Nuclear + Ponytail

**Status: thermo-nuclear and ponytail-review wired** (`.github/workflows/qa-gate.yml`)

Every PR passes this gate before merge. The `thermo-nuclear` and `ponytail-review` checks run
on each PR to `main` and fail unless the review ends with `PASS`. Both are required checks on `main`, alongside `tests` and `ux-laws`. It needs the
`CLAUDE_CODE_OAUTH_TOKEN` repo secret (from `claude setup-token`, billed to the Claude plan).

The gate runs `main`'s copy of the workflow and the skill, so a PR cannot edit the gate that reviews it.
Fork PRs fail the check.

1. **Thermo-Nuclear review**: `.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`.
   Strict maintainability review. Its approval bar decides pass or fail. Its prompt also carries the systems
   checks `factory/qa/route.py` routes to the PR's diff, built from the base branch's cards.
   The skill has `disable-model-invocation: true`, so the gate must invoke it
   explicitly (`/thermo-nuclear-code-quality-review`).
2. **Ponytail review**: `.claude/skills/ponytail-review/SKILL.md`, vendored from `vendor/ponytail/`.
   Bugs, security, load, missing tests and code to cut. A must-fix finding is a BLOCK.
3. **UX laws review**: `.claude/skills/ux-laws/SKILL.md`. Runs only when the PR touches a file matching the lane's `paths` (otherwise it passes without calling Claude); like the others it ends with PASS or BLOCK. It is a required check.

## Presumptive blockers (from the skill)

- A file pushed from under 1000 lines to over 1000 lines
- Ad-hoc branching that tangles an existing flow
- Feature checks scattered across shared code
- Unnecessary wrappers, casts, or optionality
- Duplicated helpers, or logic in the wrong layer
- A plausible "code judo" simplification left on the table

## To decide

- [x] Trigger: GitHub Action on PR
- [x] Output: pass/fail status check, review in the job summary
- [ ] Output: PR review comments
- [x] Enforcement: `thermo-nuclear`, `ponytail-review`, `ux-laws` and `tests` are required checks on `main` (branch protection)
- [x] Deterministic lanes (`.github/workflows/static.yml`): `lint` (ruff errors only, mypy on the adapter, and `factory/qa/rules.py`: checks compiled from the systems cards) and `secrets` (gitleaks over the whole history). No Claude quota.
- [x] Failure loop: the adapter sends findings to a fresh builder, up to 2 fix rounds, then marks the run blocked in `HEARTBEAT.md` for a human
- [ ] Order relative to CI

## Kaizen report

`factory/qa/kaizen_report.py` reads the gate's results on the latest PRs (merged, or from a factory run) and the run
records in `.factory-logs`. It prints the pushes each check failed and how factory runs ended, then picks the check that
failed the most pushes and drafts a task to cut that rework, quoting its latest block reasons. With `--file` it opens
that proposal as an issue labeled `kaizen`, unless one is already open. Nothing runs until the operator approves it by
sending the task to the factory. After 10 more PRs, `--prs 10` shows whether the number moved.

## Break glass: when a merge breaks the gate itself

The gate runs `main`'s copy of the workflow and the review skills (`pull_request_target`). So a merged change that
breaks the gate (the workflow, a skill, the pinned `claude` CLI) also reviews its own revert, and the revert fails or
never reports. `enforce_admins` is on, so even the admin cannot merge past it. Use this only when every PR fails the same
check for a reason in the gate, not in the PR (its review says so, or the job errors before reviewing).

1. Open the revert: `gh pr create` from `git revert <bad commit>`, or the GitHub UI's Revert button.
2. Let admins bypass protection: `gh api -X DELETE repos/svensonlabs7/the-factory/branches/main/protection/enforce_admins`
3. Merge the revert as admin: `gh pr merge <revert PR> --squash --admin`
4. Restore protection at once: `gh api -X POST repos/svensonlabs7/the-factory/branches/main/protection/enforce_admins`
   and check it with `gh api repos/svensonlabs7/the-factory/branches/main/protection/enforce_admins --jq .enabled` (`true`).
5. Push an empty commit to any open PR, or rerun its checks, to confirm the gate passes again.
6. Write it down: an `open_incidents` note in `HEARTBEAT.md` while it lasts, and a row in `knowledge/systems/GAPS.md`
   for the cause, so it is fixed and does not recur (knowledge/systems/111-postmortems.md).

Only the revert goes through this way. Fix forward through the gate once it works again.
