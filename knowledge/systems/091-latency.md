# 91. Latency

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

## What it is
Latency is how long one operation takes, from request to response. It is one of the SRE book's four golden signals. The operations a system performs span many orders of magnitude. Norvig's well-known table runs from a main-memory fetch (100 ns) and reading 1 MB from memory (250 µs), through a disk seek (8 ms), to a packet from the US to Europe and back (150 ms). Where a request's time goes is decided mostly by how many of the slow steps it takes, not by how fast the fast ones are.

Two rules from the SRE book matter most:
- **Measure success and failure separately.** It is "important to distinguish between the latency of successful requests and the latency of failed requests", because "a slow error is even worse than a fast error". Fast errors also pull the average down during an outage.
- **Measure distributions, not averages.** Collect "request counts bucketed by latencies", because the tail is where users wait (093-p99-latency.md, 094-tail-latency.md).

A latency budget is the end-to-end target split across the steps of a request. It shows which hop must get faster.

## When it is worth it
Measure latency on every user-facing path and every dependency call, from the start. Histograms per route and per outcome are cheap. Optimizing is worth it when a measured step dominates the budget of a path users wait on. Shaving microseconds off in-process code while a request makes network round trips, or tuning a background pipeline whose wall time is set by an external build, is wasted effort. Optimize the largest share first.

## How it fails
- **Average hides the problem:** a mean of 120 ms hides a long tail, or "improves" to 85 ms when 30% of requests fail in 2 ms (proof B).
- **Errors excluded from latency:** only successful requests are timed → slow timeouts, the worst user experience, are invisible.
- **Serial round trips:** a request makes N sequential network calls → latency is N times the round trip, and the fix is batching or parallelism, not faster code (027-n-plus-one-queries.md).
- **New connection per call:** every call pays DNS, TCP and TLS → about twice the round trip (proof A; 028-connection-pooling.md).
- **Wrong layer optimized:** the in-process work is tuned while one remote call is 99% of the time.
- **No budget:** nobody knows which hop may spend what, so every team assumes it is someone else's.

## Review checklist
- [ ] **Is latency measured per route and per outcome?** · Applies when: the diff adds a request path, job type or dependency call that users or the pipeline wait on. · Block if: its latency is not recorded as a distribution (histogram or percentiles) with failures included and labelled.
- [ ] **Does a request path make serial remote calls that could be batched or parallel?** · Applies when: the diff adds remote calls on a request path. · Block if: independent calls run one after another in a path where their sum is user-visible.
- [ ] **Is the optimization aimed at the largest share?** · Applies when: the diff optimizes for speed. · Block if: no measurement shows that the optimized step is a significant share of the path's latency.
- [ ] **Does the dependency call have a latency bound?** · Applies when: the diff calls a remote service. · Block if: there is no timeout below the caller's own deadline (011-timeouts.md).

## In the factory
- Where a run's time goes was measured in 060-distributed-tracing.md. Of 492 s, the sandboxed build was 406 s (82%) and waiting for the gate 82 s (17%), and the gate's critical path is the thermo-nuclear review (61 s). Latency work, if ever needed, belongs to the build and the review, not to the adapter.
- The adapter's own latency is negligible:
  - `/health` answers in 0.43 ms on localhost and `/command/data` in about 5 ms (proof A);
  - a single `gh` call is about 320 ms, and the adapter makes a few per poll (028-connection-pooling.md);
  - the Cloudflare edge round trip is about 71 ms on a reused connection and 148 ms on a new one.
- Nothing records latency per route or per outcome. 061-metrics.md and its GAPS rows already cover the missing metrics, so this card adds no row.
- Not applicable at today's load: latency budgets per hop and route-level optimization.

## Proof
`python mastery/091_latency.py` (Python 3.11, httpx, medians) on this host. The live adapter is read with `GET /health` only. The public hostname is probed without credentials, so Cloudflare Access answers 401 at its edge, which measures the edge round trip, not the full path:
```
A  Python function call                                        0.0000 ms
A  read a 4 KB file                                            0.0139 ms
A  write + fsync a 4 KB file                                   0.0505 ms
A  GET /health, live adapter on localhost (keep-alive)         0.4294 ms
A  DNS lookup factory.svensonlabs.dev                          1.0045 ms
A  HTTPS to Cloudflare edge, new connection (Access 401)     147.5064 ms
A  HTTPS to Cloudflare edge, reused connection                71.3456 ms
A  gh api rate_limit (process + TLS + GitHub)                320.4631 ms
B  mean latency, healthy: 120 ms; during an outage failing 30% fast: 85 ms (looks better)
B  split by outcome during the outage: success 120 ms, error 2 ms, error rate 30%
```
- The fsync figure is low because macOS `fsync` does not force the drive's cache to disk; `F_FULLFSYNC` does.
- `curl` on the live `/command/data`: median 5.3 ms over 5 calls.

## Related
093-p99-latency.md, 094-tail-latency.md, 092-throughput.md, 060-distributed-tracing.md, 061-metrics.md, 028-connection-pooling.md, 011-timeouts.md

## Sources
- "Monitoring Distributed Systems" (the four golden signals), Site Reliability Engineering (Google): https://sre.google/sre-book/monitoring-distributed-systems/
- "Teach Yourself Programming in Ten Years" (approximate timing of operations), Peter Norvig: https://norvig.com/21-days.html
