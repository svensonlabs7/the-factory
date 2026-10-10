# Factory QA Gate

Thermo-Nuclear Code Quality Review is the QA gate.

## What QA Does

Runs on every PR diff before `/autopilot-full` marks it ready to merge.
Returns PASS or BLOCK with specific findings.

## The Gate

Loaded from: `.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`

Hard blocks:
- Any file > 1000 lines
- Ad-hoc conditionals without abstraction
- Risky logic without test coverage
- Structural regressions (complexity, nesting)

## Verdict Format

```
THERMO-NUCLEAR REVIEW: [PASS | BLOCK]
Reason: <one sentence>
Findings: [HARD BLOCK | WARNING | JUDO OPPORTUNITY]
Required before merge: <list>
```

## Integration (TODO)

- [ ] Wire QA gate to OpenHands PR creation step
- [ ] Auto-run on every diff before `/autopilot-full`
- [ ] Log results to HEARTBEAT.md
- [ ] Slack/Grok Bot notification on BLOCK
