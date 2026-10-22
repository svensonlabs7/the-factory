# 63. SLOs

Track: C. Observability · Status: proven · Updated: 2026-10-18

## What it is
A service level objective (SLO) is a target for an SLI over a window, such as "90% of runs ship within 60 minutes, over a rolling 90 days". It turns "is it reliable enough?" into a number both builders and users agreed on. The SRE book's rules:
- never aim for 100%, because each extra nine costs far more and users rarely notice;
- base the target on what users need, not on today's performance;
- keep SLOs few and simple;
- start loose and tighten over time.

The gap between the SLO and 100% is the error budget (065-error-budgets.md), the amount of failure you have agreed to spend. A target is meaningful only if the window holds enough events to measure it. With few events, the measured value is mostly noise.

## When it is worth it
It is worth it when someone depends on the service and decisions are being made about reliability versus speed: whether to ship, or to fix. One or two SLOs per service, written down, are enough to start. Per-customer SLOs, contractual SLAs and multi-tier targets come with paying users and many services. For a low-volume pipeline, an outcome SLO needs a long window, and tight "nines" are unmeasurable.

## How it fails
- **Aiming for 100%:** any failure breaches it → it is ignored, or all effort goes to reliability users cannot perceive.
- **Copying current performance:** today's lucky number becomes a commitment the design cannot keep.
- **Too few events in the window:** a monthly SLO over a few dozen events flips between "met" and "missed" by chance → decisions are made on noise.
- **Nines with no denominator:** "99.9%" over 60 events a month allows 0.06 failures, so one bad run breaks it and the target means nothing.
- **Too many SLOs:** none of them changes a decision.
- **SLO without an SLI:** a target for a number nobody records.

## Review checklist
- [ ] **Is the target below 100% and tied to user need?** · Applies when: the diff sets or changes an SLO. · Block if: the target is 100%, or is justified only by current performance.
- [ ] **Does the window hold enough events for the target?** · Applies when: the diff sets an SLO target and window. · Block if: the expected number of failures allowed per window (events × (1 − target)) is below about 1, or the window's sampling noise is wider than the gap between target and expected performance.
- [ ] **Does the SLO rest on a recorded SLI?** · Applies when: the diff adds an SLO. · Block if: the SLI it targets is not computed from recorded events (see 064-slis.md).
- [ ] **Is there a small number of SLOs, each tied to a decision?** · Applies when: the diff adds SLOs. · Block if: an SLO has no stated action when it is missed.

## In the factory
- No SLO is defined. That is a decision for the operator, and it depends on the SLI gap logged in 064-slis.md, so no separate row is added.
- Suggested starting set, loose by design:
  1. **Autonomous delivery:** 80% of triggered runs merged without human commits, over a rolling 90 days.
  2. **Latency:** 90% of runs open a PR within 60 minutes of trigger, over 90 days.
  3. **Availability:** an authenticated probe of `/health` through the tunnel succeeds in 99% of minutes over 30 days. Do not use `alive_at` for this: 057-liveness-readiness-probes.md showed it keeps updating while the server cannot answer, so it proves the process exists, not that the factory is reachable.

  Minutes give about 43,000 events a month, so a 99% target is measurable there, and run outcomes are not.
- Not applicable at today's load: SLAs, per-tenant SLOs and tight nines on run outcomes. There are about 60 runs a month at most (`MAX_RUNS_PER_DAY` is 30, real use is a few a day).

## Proof
`python3 -I knowledge/systems/proofs/063_slos.py` (standard library only; A starts from the real autonomous-delivery SLI, 5 of 8):
```
A  5/8 = 62%: the true rate is somewhere in 31%..86% (95%)
A  48/60 = 80%: the true rate is somewhere in 68%..88% (95%)
A  480/600 = 80%: the true rate is somewhere in 77%..83% (95%)
B  target 80.0% over 60 runs/month allows 12.0 misses a month
B  target 90.0% over 60 runs/month allows 6.0 misses a month
B  target 99.0% over 60 runs/month allows 0.6 misses a month
B  target 99.9% over 60 runs/month allows 0.1 misses a month
B  true rate 85%, SLO 90%: the month's number says 'met' in 19% of months
B  true rate 92%, SLO 90%: the month's number says 'met' in 80% of months
```
Today's 8 runs cannot tell a good factory from a mediocre one. Even 60 runs a month misjudge a 90% target in about one month in five, in both directions. Longer windows narrow the interval: 600 events give ±3 points.

## Related
064-slis.md, 065-error-budgets.md, 062-alerts.md, 061-metrics.md, 057-liveness-readiness-probes.md, 093-p99-latency.md

## Sources
- "Embracing Risk", Google SRE book: https://sre.google/sre-book/embracing-risk/
- "Service Level Objectives", Google SRE book: https://sre.google/sre-book/service-level-objectives/
