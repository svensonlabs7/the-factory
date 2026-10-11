# QA Gate — Thermo-Nuclear + Ponytail

**Status: thermo-nuclear and ponytail-review wired** (`.github/workflows/qa-gate.yml`)

Every PR passes this gate before merge. The `thermo-nuclear` and `ponytail-review` checks run
on each PR to `main` and fail unless the review ends with `PASS`. Both are required checks on `main`, alongside `tests`. It needs the
`CLAUDE_CODE_OAUTH_TOKEN` repo secret (from `claude setup-token`, billed to the Claude plan).

The gate runs `main`'s copy of the workflow and the skill, so a PR cannot edit the gate that reviews it.
Fork PRs fail the check.

1. **Thermo-Nuclear review**: `.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`.
   Strict maintainability review. Its approval bar decides pass or fail.
   The skill has `disable-model-invocation: true`, so the gate must invoke it
   explicitly (`/thermo-nuclear-code-quality-review`).
2. **Ponytail review**: `.claude/skills/ponytail-review/SKILL.md`, vendored from `vendor/ponytail/`.
   Bugs, security, load, missing tests and code to cut. A must-fix finding is a BLOCK.

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
- [x] Enforcement: `thermo-nuclear`, `ponytail-review` and `tests` are required checks on `main` (branch protection)
- [x] Failure loop: the adapter sends findings to a fresh builder, up to 2 fix rounds, then marks the run blocked in `HEARTBEAT.md` for a human
- [ ] Order relative to CI
