# 64. SLIs

Track: C. Observability · Status: proven · Updated: 2026-10-18

## What it is
A service level indicator (SLI) is a carefully defined measure of how well a service is doing, from the point of view of the people who use it. The SRE workbook's form is one ratio: good events ÷ valid events, between 0% and 100%. A **specification** says what users care about ("feature requests that end up shipped"). An **implementation** says how it is measured, and where ("PRs merged, counted from GitHub"). The menu differs by kind of system:
- **Request-driven:** availability, latency, quality.
- **Pipelines and batch:** freshness, correctness, coverage.

Measure as close to the user as you can. A server counting its own successes misses failures it cannot see, and counts as "good" outcomes the user would call bad.

## When it is worth it
Every service with users should have one to three SLIs that match what those users want, before anyone argues about reliability targets. Several SLIs per user journey, client-side instrumentation and SLI pipelines are for large, user-facing products. A single pipeline needs one outcome SLI and one latency SLI, computed from records it already keeps.

## How it fails
- **Measuring what is easy:** "the job exited 0" or "the endpoint returned 200" is counted good while the user got a broken or unshipped result.
- **Measuring at the server:** requests that never arrived, and results nobody used, are invisible.
- **"Valid" undefined:** retries, test traffic, rejected input and human-finished work are counted inconsistently, so the number moves for reasons that are not about reliability.
- **Too many SLIs:** nobody knows which one matters.
- **An SLI no one can compute:** the outcome it needs (merged, reverted, used) is never recorded.

## Review checklist
- [ ] **Does a new user-facing flow or pipeline have an outcome SLI?** · Applies when: the diff adds a service, job type or pipeline that users depend on. · Block if: there is no stated good ÷ valid ratio for whether users got the result they asked for.
- [ ] **Is the SLI measured at the user's outcome, not the server's exit code?** · Applies when: the diff defines or changes an SLI. · Block if: "good" is the service's own success flag while a user-visible outcome (delivered, merged, rendered, used) is available.
- [ ] **Are valid and good events defined explicitly?** · Applies when: the diff defines an SLI. · Block if: it does not say which events are excluded (tests, rejected input, human takeover) and why.
- [ ] **Is the data the SLI needs recorded?** · Applies when: the diff defines an SLI. · Block if: the good or valid events are not written anywhere the SLI can be computed from.

## In the factory
- `factory/intake/webhook_adapter.py` (`_finish`): every run records a terminal `status` with `queued_at`, `started_at` and `finished_at`, and `pr_url`. Server-side SLIs (completion rate, run time) can be computed from these. Right.
- Today's only success signal, `status == "completed"`, means the gate passed. It disagrees with what was actually shipped in both directions (proof below), so it is a server-side proxy, not the outcome.
- Gap (low): the factory defines no outcome SLI, and does not record what happened to each PR (merged, closed, merged after human commits). The spec should be "share of triggered runs whose PR merged without human commits", plus "time from trigger to merge" (see GAPS.md). This relates to the `last_pr_merged` row from 044-backpressure.md.
- Not applicable at today's load: client-side instrumentation and SLI pipelines. A dozen runs a month can be scored from `meta.json` plus `gh pr view`.

## Proof
`python3 -I scratchpad/mastery/064_slis.py .factory-logs`, using every run on disk and each PR's state from GitHub:
```
  8fb2c8b4  status=completed PR #48  MERGED
  b3c60871  status=blocked   PR #49  MERGED
  1e8e28c7  status=failed    PR #50  MERGED
  acec82e0  status=completed PR #52  MERGED
  7ed9194b  status=completed PR #53  MERGED
  90cb4f17  status=completed PR #54  MERGED
  4981e691  status=completed PR #55  CLOSED
  920d7293  status=completed PR #56  MERGED
SLI server-side  'run completed':  6/8 = 75%
SLI user-facing  'PR merged':      7/8 = 88%
  counted good by the server, not shipped: [('4981e691', 55)]
  counted bad by the server, shipped anyway (a human finished it): [('b3c60871', 49), ('1e8e28c7', 50)]
```
"Completed and merged", the factory delivering on its own, is 5/8 = 62%. Neither single signal says that. PR #55 passed every gate check and was closed because its fix did not work against real Docker, which is a correctness failure that only post-merge verification would count.

## Related
063-slos.md, 065-error-budgets.md, 061-metrics.md, 058-monitoring.md

## Sources
- "Implementing SLOs", Google SRE workbook: https://sre.google/workbook/implementing-slos/
- "Service Level Objectives", Google SRE book: https://sre.google/sre-book/service-level-objectives/
