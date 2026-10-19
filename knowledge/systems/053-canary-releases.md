# 53. Canary Releases

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

## What it is
A canary release sends a new version to a small part of production first, such as a few percent of servers or users, and compares it with the rest (the control) before rolling it out further. If the canary's error rate or latency is worse than the control's, the rollout stops and the canary is rolled back. Only that small slice ever saw the bad version.

Google's SRE workbook defines canarying as "a partial and time-limited deployment of a change in a service and its evaluation." It is effectively an A/B test.

Three rules make it work:
- **Compare against a control running at the same time,** not against "before". Load and time of day move every metric.
- **Use a few user-facing metrics** that the change can affect: error rate and latency.
- **Give the canary enough traffic and time** to produce a signal. A handful of requests proves nothing.

## When it is worth it
A canary is worth it when a bad release would hurt many users, and traffic is high enough for a small slice to show a difference within minutes or hours. It needs a way to route a slice of traffic, metrics split by version, and an automatic or practised rollback. At low volume a canary cannot tell a regression from noise in any useful time. A deliberate trial (one real run of the changed system, inspected end to end) gives more signal than waiting for statistics.

## How it fails
- **Before/after comparison:** the canary is judged against yesterday's or this morning's numbers → load and time of day trigger false rollbacks, or hide real regressions.
- **Canary too small or too short:** too few requests to separate a regression from noise → a bad version passes and rolls out.
- **Wrong metrics:** CPU or host-level noise, or client errors (4xx) counted as failures → noise decides.
- **Not representative:** the canary gets only off-peak traffic, internal users or one request type → bugs that appear under load or with real inputs are missed.
- **Mixed versions incompatible:** the canary writes state that the control cannot read (see 055-rollbacks.md).
- **Changes that cannot be canaried treated as if they were:** config pushed globally, or a schema change → everyone gets it at once, whatever the rollout tool shows.

## Review checklist
- [ ] **Is the canary compared with a concurrent control?** · Applies when: the diff adds or changes canary analysis or rollout promotion rules. · Block if: promotion compares the canary with a before-deploy baseline instead of the control serving at the same time.
- [ ] **Are the canary's size and duration enough for its metrics?** · Applies when: the diff sets canary percentage, duration or promotion thresholds. · Block if: at the expected traffic, the canary cannot collect enough requests in its window to detect the regression it is meant to catch.
- [ ] **Do the metrics reflect users and the change?** · Applies when: the diff selects canary metrics. · Block if: they are host-level noise only, or they count client errors (4xx) as canary failures.
- [ ] **Does a global change still get a staged check?** · Applies when: the diff changes behaviour that every request or run uses at once (global config, a prompt template, a review workflow or skill, a sandbox image); comment-only and doc-only edits do not count. · Block if: the PR shows no trial against the real system (a trial run, a shadow or advisory phase), and the change cannot be undone by a restart.
- [ ] **Is a canary justified at this volume?** · Applies when: the diff adds canary infrastructure (traffic splitting, version-split metrics, automated analysis). · Block if: traffic is too low for the canary to reach a verdict before a manual trial would.

## In the factory
- Every factory change ships to everything at once:
  - `factory/intake/webhook_adapter.py:251` (`TASK_PROMPT_TEMPLATE`) and `factory/build/run_agent.py` change every run.
  - `.github/workflows/qa-gate.yml` and the review skills change the review of every PR at once, because `pull_request_target` uses main's copy.

  There is no slice to canary.
- The volume rules a canary out: about 3 runs a day, with a 25% non-completion rate in the 8 live run records (6 completed, 1 blocked, 1 failed). A canary would need about 60 runs per arm, 40 days, to catch failures doubling to 50% nine times out of ten (proof C). A deliberate trial run after a change catches the same bug the same day. The missing trial is already recorded as the Error Budgets row in GAPS.md (no live verification of sandbox changes, PR #55).
- The gate's equivalent of a canary is an advisory phase: run a new or changed review lane as a check that is not yet required, read its verdicts on real PRs, then make it required. Nothing in the repo records whether lanes were introduced that way.
- Not applicable at today's load: traffic splitting, version-split metrics and automated canary analysis.

## Proof
`python3 -I scratchpad/mastery/053_canary.py` is a seeded simulation:
```
A  deploy to all:  1,178 failed requests (alarm after 1 min, 5 min to roll back)
A  5% canary:      8 failed requests caused by the release (caught at minute 1, 500 canary requests)
B  good release at peak, before/after: z = 5.4 -> rolled back for nothing
B  good release at peak, vs control:  z = -1.7 -> passes
C   5 runs per arm (  3.3 days at 3 runs/day): regression detected 19% of the time
C  20 runs per arm ( 13.3 days at 3 runs/day): regression detected 50% of the time
C  60 runs per arm ( 40.0 days at 3 runs/day): regression detected 90% of the time
```
- A: at 10,000 requests a minute, the canary cuts the damage about 150 times.
- B: a before/after comparison rolls back a good release when peak load lifts everyone's errors. The concurrent control does not.
- C: at the factory's volume, statistics take weeks.

## Related
052-blue-green-deployment.md, 054-rolling-deployments.md, 055-rollbacks.md, 051-feature-flags.md, 064-slis.md, 065-error-budgets.md

## Sources
- "Canarying Releases", The Site Reliability Workbook (Google), chapter 16: https://sre.google/workbook/canarying-releases/
- "CanaryRelease", Danilo Sato, martinfowler.com: https://martinfowler.com/bliki/CanaryRelease.html
