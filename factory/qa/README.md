# QA Gate — Thermo-Nuclear + Ponytail

**Status: thermo-nuclear wired** (`.github/workflows/qa-gate.yml`)

Every PR passes this gate before merge. The `thermo-nuclear` check runs
on each PR to `main` and fails unless the review ends with `PASS`. It needs the
`CLAUDE_CODE_OAUTH_TOKEN` repo secret (from `claude setup-token`, billed to the Claude plan).

1. **Thermo-Nuclear review**: `.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`.
   Strict maintainability review. Its approval bar decides pass or fail.
   The skill has `disable-model-invocation: true`, so the gate must invoke it
   explicitly (`/thermo-nuclear-code-quality-review`).
2. **Ponytail check**: is the diff the minimum needed? Flag speculative code.

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
- [x] Enforcement: `thermo-nuclear` is a required check on `main` (branch protection)
- [ ] Failure loop: send findings back to Build, cap the retries, then escalate to a human
- [ ] Order relative to CI
