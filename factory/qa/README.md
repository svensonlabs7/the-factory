# QA Gate — Thermo-Nuclear + Ponytail

**Status: stub**

Every PR passes this gate before merge.

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

- [ ] Trigger: GitHub Action on PR, or a step in the build pipeline
- [ ] Output: PR review comments plus a pass/fail status check
- [ ] Failure loop: send findings back to Build, cap the retries, then escalate to a human
- [ ] Order relative to CI
