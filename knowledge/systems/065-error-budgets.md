# 65. Error Budgets

Track: C. Observability · Status: proven · Updated: 2026-10-18

## What it is
An error budget is the amount of unreliability an SLO allows: 100% minus the target, over the SLO's window. With a 99.9% monthly SLO, 0.1% of the month's requests may fail. The budget turns reliability into a shared, spendable resource. While budget remains, teams ship features, experiments and risky changes. When it is spent, an agreed error budget policy takes over.

The SRE workbook's example policy:
- **Budget exceeded over four weeks:** stop changes except P0 and security fixes until the service is back within SLO.
- **One incident uses more than 20% of the budget:** it gets a postmortem with a P0 action item.
- **One class of failure uses more than 20% over a quarter:** it gets a P0 item on the next plan.

It is explicitly not a punishment. It is a pre-agreed rule, so the data decides when reliability beats features, instead of an argument.

## When it is worth it
It is worth it once there is an SLO with enough events to measure (see 063-slos.md) and a real tension between shipping and stabilising. The policy should be agreed in writing before the budget runs out. Automated release gates tied to budget, per-team budgets and burn-rate dashboards are for organisations with many services and teams. For one operator, the value is the rule itself: when the budget is spent, fix reliability before adding features.

## How it fails
- **No policy:** the budget is spent and nothing changes → the SLO is decoration.
- **Policy written after the breach:** every overrun becomes a negotiation.
- **Budget on an unmeasurable SLO:** a 99% target over a few dozen events makes one failure 1,000%+ of the budget → permanent freeze, so the policy is ignored.
- **Not attributing the spend:** the budget is used up but nobody knows by what → the fix is aimed at the wrong cause.
- **Treated as punishment:** people hide incidents or argue about counting.

## Review checklist
- [ ] **Does a new SLO come with a written budget policy?** · Applies when: the diff adds or changes an SLO. · Block if: there is no agreed action for when the budget is spent.
- [ ] **Is the budget large enough to spend?** · Applies when: the diff sets an SLO target. · Block if: the budget per window is under about one event, so a single miss exhausts it.
- [ ] **Are misses attributed to causes?** · Applies when: the diff records SLO misses or failures. · Block if: a miss is recorded without a cause category that lets the spend be grouped.
- [ ] **When the budget is spent, are features paused for reliability work?** · Applies when: a feature change is proposed while the service is over budget. · Block if: it is not a P0 or security fix and the budget is exceeded, unless the operator has explicitly overridden the policy.

## In the factory
- No SLO or budget policy exists yet (see 063-slos.md and the SLI row in GAPS.md). The run records are enough to compute one by hand (proof below).
- Against the starter SLO (80% autonomous delivery), the 8 runs on record have used 188% of their budget. Three causes each used 63%:
  1. The plan usage limit: P0 already done, PR #52 added pause and rerun.
  2. The gate blocking until fix rounds ran out: partly addressed by #54 (fix rounds see earlier findings). The crashed-reviewer misclassification is still open in the Retries row.
  3. The gate passing a change that did not work (#55): nothing addresses this. The gate's tests use a fake Docker, so a change to sandbox or infra behaviour can pass every check and still fail for real. It was caught only by a manual live test (see GAPS.md).
- With the budget spent, the policy says to pause factory feature work and fix reliability first. That is the GAPS list, starting with the high row.
- Not applicable at today's load: budget-gated release automation and burn-rate dashboards.

## Proof
`python3 -I scratchpad/mastery/065_error_budget.py .factory-logs`, using the real runs, each PR's state from GitHub, and each failed run's raw log for the cause:
```
runs 8, SLO 80% -> error budget 1.6 misses; used 3 = 188% of budget
  gate kept blocking (fix rounds did not converge)   1 miss = 63% of budget -> P0 item (over 20%)
  plan usage limit                                   1 miss = 63% of budget -> P0 item (over 20%)
  gate passed a change that did not work (closed)    1 miss = 63% of budget -> P0 item (over 20%)
policy: budget exceeded -> freeze factory feature work; reliability fixes only
same runs under a 99% SLO: budget 0.08 misses -> one miss is 1250% of budget
```

## Related
063-slos.md, 064-slis.md, 111-postmortems.md, 062-alerts.md

## Sources
- "Example Error Budget Policy", Google SRE workbook: https://sre.google/workbook/error-budget-policy/
- "Embracing Risk", Google SRE book: https://sre.google/sre-book/embracing-risk/
