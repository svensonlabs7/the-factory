# Thermo-Nuclear Code Quality Review

## disable-model-invocation: true

This skill is a structured code review gate, not a conversation.
It runs before any PR merges. It does not invoke the model for
conversational responses — it produces a pass/block verdict.

## Philosophy: Code Judo

The best code reviews don't just catch bugs. They restructure things
to **delete whole layers**. A 500-line file that becomes a 50-line
file after a good review is the ideal. Less code = less surface area =
fewer bugs = faster iteration.

Code judo means:
- Find the abstraction that eliminates 10 ad-hoc cases
- Find the module boundary that makes the conditional impossible
- Find the data structure that makes the algorithm obvious

## Hard Rules (Block on Any)

1. **No file > 1000 lines.** If a file is growing past this, it has
   more than one responsibility. Split it.

2. **No ad-hoc conditionals.** Every `if (type === 'X')` branch that
   doesn't map to a clean abstraction is a smell. If you're adding
   the third case to an existing if-chain, you owe the reviewer a
   structural proposal.

3. **Risky logic requires tests.** Any function that touches money,
   auth, data mutation, or external state ships with a test.
   98% threshold (Ponytail 5 enforced).

4. **No structural regressions.** A PR that adds a file > 1000 lines,
   increases cyclomatic complexity on a hot path, or deepens nesting
   beyond 4 levels is blocked unless there's an explicit waiver with
   a named human approver.

## Review Checklist

Before marking any PR as approved, verify:

- [ ] All files touched are < 1000 lines after the change
- [ ] No new ad-hoc type/kind/variant conditionals without abstraction
- [ ] Risky logic has test coverage
- [ ] Cyclomatic complexity on hot paths is flat or reduced
- [ ] No new magic numbers or magic strings (use constants)
- [ ] Error paths are explicit and tested
- [ ] The PR description explains WHY, not just WHAT

## Verdict Format

```
THERMO-NUCLEAR REVIEW: [PASS | BLOCK]

Reason: <one sentence>

Findings:
- [HARD BLOCK] <specific violation>
- [WARNING] <concern that doesn't block but should be addressed>
- [JUDO OPPORTUNITY] <structural refactor that would delete code>

Required before merge: <list of changes required for PASS>
```

## Integration

This skill is invoked by the factory QA gate in `factory/qa/`.
It runs on every PR diff before /autopilot-full marks it ready to merge.

## Reference

Source: cursor/plugins/cursor-team-kit
Philosophy: poteto (React core team, ex-Meta/Netflix/Cursor)
