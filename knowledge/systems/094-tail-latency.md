# 94. Tail Latency

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)gather\(|as_completed|fan.?out|\bhedg|speculativ`

## What it is
Tail latency is the slow end of the latency distribution (p99, p99.9), and at scale it, not the median, decides how a system feels. Dean and Barroso's "The Tail at Scale" shows why. When one user request fans out to many servers and waits for all of them, rare slowness becomes common. A server that answers in 10 ms but takes a second once in 100 requests makes 63% of user requests slow when each request needs 100 such servers. In Google's measurement of a real fan-out service, one leaf's p99 was 10 ms, while waiting for all leaves took 140 ms at p99. Waiting for the slowest 5% was responsible for half of that total.

The paper's remedy is to make systems "tail-tolerant" rather than to try to remove all variability:
- **Hedged requests:** send a second copy to another replica after the first has been outstanding past the 95th-percentile latency, and use whichever answers first. In a Bigtable benchmark, hedging after 10 ms cut the p99.9 for reading 1,000 values "from 1,800ms to 74ms while sending just 2% more requests".
- **Tied requests:** send both copies at once and cancel the slower.
- **Micro-partitioning, latency-induced probation of slow servers, and "good enough" partial results.**

All of these spend extra work or redundancy to buy a shorter tail.

## When it is worth it
Tail-tolerant techniques are worth it when requests fan out to many parallel sub-requests, or many users hit the slow end at high volume, and the operations are idempotent and replicated so a duplicate is cheap and safe. Hedging doubles cost for the hedged fraction, so it fits read-only, cheap, replicated calls. It does not fit expensive or side-effecting work. With little fan-out and low volume, measure the tail (093-p99-latency.md) and fix the slowest component directly instead.

## How it fails
- **Fan-out amplification ignored:** each backend's p99 looks fine, but a page that waits for 100 of them is slow most of the time (proof A).
- **Hedging non-idempotent or expensive work:** the duplicate charges twice, sends twice, or doubles the cost of a scarce resource.
- **Hedging too early:** a hedge threshold below the typical latency duplicates most requests, doubles load, and makes the tail worse under pressure.
- **No cancellation:** losing copies keep running → wasted capacity that lengthens everyone's queue.
- **Synchronized background work:** GC, compaction or cron jobs on many machines at random times → some server is always slow, so the fan-out always waits.
- **Critical path ignored:** optimizing jobs that are not the slowest leaves the end-to-end latency unchanged.

## Review checklist
- [ ] **Does a request wait on many parallel sub-requests?** · Applies when: the diff adds a fan-out (parallel calls, scatter-gather, a matrix of jobs) whose result waits for all of them. · Block if: there is no per-sub-request timeout or partial-result path, so the slowest member sets the latency without bound.
- [ ] **Is hedging limited to safe, cheap work?** · Applies when: the diff adds hedged, duplicated or speculative requests. · Block if: the hedged operation is not idempotent, is expensive or quota-bound, is not cancelled when the first answer arrives, or is hedged before roughly its p95 latency.
- [ ] **Is the latency work aimed at the critical path?** · Applies when: the diff speeds up one branch of a parallel fan-out. · Block if: that branch is not the slowest one on the measured critical path.
- [ ] **Is the tail measured where users experience it?** · Applies when: the diff adds a fan-out endpoint. · Block if: only per-backend latency is measured, not the end-to-end latency of the combined request.

## In the factory
- The gate is a fan-out: a PR passes only when all six required checks finish, so the gate's latency is its slowest job. Across 15 successful `qa-gate` runs, thermo-nuclear (the Opus review) was the slowest job every time: median 43 s, maximum 61 s, against 24 s for the next slowest. `tests` took 23–35 s.
  - Shortening the other jobs would change nothing.
  - Hedging the review (running it twice) would double usage of the Claude plan, the factory's scarcest resource (061-metrics.md). That is the wrong trade.
- The dashboard's cold load is also a fan-out: one `gh` call per PR on 8 threads, so its latency is the slowest call. It is cached and small today (027-n-plus-one-queries.md).
- Not applicable at today's load: hedged and tied requests, micro-partitioning and server probation.

## Proof
`python3.11 -I knowledge/systems/proofs/094_tail.py '<runs>'`. A and B are seeded simulations: a server at 10 ms, 1% of requests at 1 s. C uses per-job durations from the 15 most recent successful `qa-gate` runs (`gh run view --json jobs`, read-only):
```
A  fan-out to   1 servers:   1.0% of user requests take 1 s (formula 1-0.99^N =   1.0%)
A  fan-out to  10 servers:   9.6% of user requests take 1 s (formula 1-0.99^N =   9.6%)
A  fan-out to 100 servers:  62.8% of user requests take 1 s (formula 1-0.99^N =  63.4%)
B  no hedging:              p50   10.0 ms  p99    15.0 ms  p99.9  1000.0 ms
B  hedge after p95 (14.6 ms): p50   10.1 ms  p99    19.6 ms  p99.9    28.8 ms; extra requests 5.0%
C  15 qa-gate runs: gate time = slowest job, median 43 s, max 61 s; slowest job thermo-nuclear in 15/15; second-slowest median 24 s
```
Hedging cut p99.9 by 35 times for 5% more requests. It raised p99 slightly, because a hedged copy starts only after the p95 delay.

## Related
093-p99-latency.md, 091-latency.md, 027-n-plus-one-queries.md, 061-metrics.md, 014-idempotency.md, 011-timeouts.md

## Sources
- Jeffrey Dean and Luiz André Barroso, "The Tail at Scale", Communications of the ACM 56(2), 2013: https://www.barroso.org/publications/TheTailAtScale.pdf
- Publication page, Google Research: https://research.google/pubs/the-tail-at-scale/
