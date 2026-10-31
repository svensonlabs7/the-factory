# 93. P99 Latency

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)\bp9[59]\b|percentile|quantile|histogram`

## What it is
The p99 latency is the value that 99% of requests come in under: the slowest 1% take longer. Percentiles describe the experience averages hide (091-latency.md). They are also easy to compute wrongly, and a wrong p99 is worse than none, because it gives false confidence.

Three mistakes recur:
- **Percentiles do not average or add.** Prometheus warns that "aggregating the precomputed quantiles from a summary rarely makes sense". Merge the underlying histograms, then take the percentile. A histogram's estimate is only as precise as its buckets: the error "is limited by the width of the bucket the quantile is located in".
- **Coordinated omission.** A load generator that waits for each response before sending the next stops sending exactly when the system stalls, so the stall leaves one slow sample instead of the many requests that real users would have queued. The HdrHistogram README's example is a 100-second pause sampled every 10 ms: the raw data shows about 99.99% of results at 1 ms or below, which it calls "not right". HdrHistogram's `recordValueWithExpectedInterval` corrects for it.
- **Too few samples.** A p99 needs enough samples for the slowest 1% to be more than one or two values.

## When it is worth it
Track p99 (and p99.9 at scale) for every user-facing or SLO-bearing path with enough traffic, recorded as histograms that can be merged across instances and windows. Load tests must schedule requests open-loop (at fixed intended times) and measure from the intended start. With small samples, report the maximum and the raw values instead. A p99 over a few dozen events is noise that looks like a statistic.

## How it fails
- **Averaged percentiles:** a dashboard averages per-host p99s, or per-minute p99s over an hour → a number that is neither the fleet's nor the hour's p99. It can be too high or too low (proof A).
- **Coordinated omission:** a closed-loop benchmark reports p99 = 1 ms for a service that makes 10% of its users wait up to a second (proof B).
- **Coarse buckets:** buckets at 100, 200, 300 and 450 ms report a 320 ms spike as about 443 ms, or hide a change entirely.
- **Too few samples:** the p99 of 50 requests ranges from 44 to 250 ms between identical repeats (proof C), so a "regression" can be noise.
- **Percentile of the wrong population:** errors excluded, or only one endpoint's p99 reported for a mixed page.
- **Timeouts set from the average:** a timeout at twice the mean cuts off the normal tail → spurious failures and retries.

## Review checklist
- [ ] **Are latency percentiles computed from mergeable distributions?** · Applies when: the diff adds latency metrics or a dashboard or report of percentiles. · Block if: it averages or sums precomputed percentiles across hosts or windows, instead of merging histograms (or raw samples) and computing the percentile once.
- [ ] **Does the load test avoid coordinated omission?** · Applies when: the diff adds or changes a load test or benchmark that reports latency percentiles. · Block if: it waits for each response before sending the next and measures from the actual send time, instead of scheduling requests open-loop and measuring from the intended send time.
- [ ] **Is there enough data for the percentile claimed?** · Applies when: the diff reports or alerts on a high percentile. · Block if: the window holds too few samples for that percentile to be stable (rule of thumb: at least 100/(100−p) × 10, so 1,000 for p99), with no minimum-count guard.
- [ ] **Are timeouts set from the observed tail?** · Applies when: the diff sets a timeout for an operation with measured durations. · Block if: it is set from a mean, or below the observed maximum, with no margin above the tail.

## In the factory
- No percentile is computed anywhere. Latency metrics are missing altogether, already recorded under 061-metrics.md, so this card adds no row.
- Where tails matter, the factory has too few events for percentiles. Its timeouts are set, rightly, from the observed maximum with a wide margin:
  - two timed build rounds, 315 s and 406 s, against `AGENT_TIMEOUT = 1800` s (`factory/intake/webhook_adapter.py:53`), 4.4 times the maximum;
  - the slowest gate job, thermo-nuclear at 61 s, against `CHECKS_TIMEOUT = 1200` s (`:63`).

  Reporting a "p99 build time" from 2 or 8 runs would be noise (proof C). Report the maximum, and revisit the margins as runs accumulate.
- The live dashboard endpoint's own tail is flat: over 200 local requests, p50 5.1 ms, p99 7.5 ms, max 9.5 ms (proof D).
- Not applicable at today's load: histogram metrics, latency SLO percentiles and open-loop load testing.

## Proof
`python3.11 -I knowledge/systems/proofs/093_p99.py`. A to C are seeded simulations. D is 200 sequential `curl` requests to the live adapter's `/command/data` on localhost:
```
A  p99 host A 62 ms, host B 592 ms; average of the two 327 ms; true fleet p99 62 ms
B  closed loop (coordinated omission)   samples  4914: p50     1.0 ms  p99     1.0 ms
B  open loop (corrected)                samples  6000: p50     1.0 ms  p99   901.0 ms
C      50 samples: p99 estimate ranges   44.2- 249.9 ms over 200 repeats (stdev  25.6)
C   10000 samples: p99 estimate ranges   76.7-  86.5 ms over 200 repeats (stdev   1.9)
D  live /command/data, 200 requests: p50 5.1 ms, p99 7.5 ms, max 9.5 ms
```
In B the service stalls for 1 s every 10 s. The closed-loop generator sends almost nothing during each stall, so its p99 says 1 ms.

## Related
091-latency.md, 094-tail-latency.md, 061-metrics.md, 063-slos.md, 064-slis.md, 011-timeouts.md, 092-throughput.md

## Sources
- "Histograms and summaries", Prometheus documentation: https://prometheus.io/docs/practices/histograms/
- HdrHistogram README ("Corrected vs. Raw value recording calls"): https://github.com/HdrHistogram/HdrHistogram
