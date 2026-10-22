# 10. Circuit Breakers

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
A circuit breaker sits in front of calls to a dependency and counts failures. While the dependency works, the breaker is closed and calls pass through. After a threshold of failures it opens: calls fail at once without reaching the dependency, so callers stop waiting on timeouts and the dependency gets room to recover. After a set time it goes half-open and lets a trial call through: success closes it, failure opens it again. It answers a different question from retries. Retries ask whether this call might succeed if repeated. A breaker asks whether calls are worth making at all right now.

## When it is worth it
It is worth it when many concurrent callers share a dependency that can fail for minutes, and each failed call is expensive to wait for (long timeouts, held threads or connections), so one outage would exhaust the callers too. The open state then needs a useful answer: a cached value, a degraded feature, or "try later". It is not worth it with one caller doing serial work, where a failure already stops the line, with a queue whose failed work can wait or be dead-lettered, or where bounded retries with backoff are enough. A breaker adds a mode that is hard to test, and it rejects calls that would have succeeded.

## How it fails
- **No breaker in front of a hung dependency:** every caller waits the full timeout → threads, connections and queue slots fill up, and the outage spreads to callers that never touch the dependency.
- **Breaker during a partial outage:** the dependency still serves half its calls, but the breaker keeps tripping → success drops below what plain calls would get.
- **Slow to close:** the dependency recovers, but the breaker stays open for its full window, or its trial call hits a leftover failure → good calls are rejected after recovery.
- **One breaker for many independent targets:** one bad shard, host or region trips the breaker for all of them.
- **Tripping on the caller's own errors:** validation errors, 4xx or "not found" count as failures → a few bad requests cut off a healthy dependency.
- **Silent state:** nobody sees that the breaker is open → it looks like an unexplained outage.

## Review checklist
- [ ] **Does a breaker protect something that needs it?** · Applies when: the diff adds a circuit breaker. · Block if: the protected call is local, serial with one caller, or already behind a queue, and the diff gives no concurrency or cost reason for the breaker.
- [ ] **Do only dependency failures trip it?** · Applies when: the diff adds or configures a breaker. · Block if: client-side errors (validation, 4xx other than 429, not found) count toward tripping.
- [ ] **Does the open state give the caller a deliberate answer?** · Applies when: the diff adds a breaker. · Block if: the open state raises a generic error and no caller handles it (no fallback, no "try later", no degraded result).
- [ ] **Is there one breaker per independent target?** · Applies when: the diff adds a breaker in front of several hosts, shards, regions or tenants. · Block if: a single breaker covers targets that fail independently.
- [ ] **Is each state change visible?** · Applies when: the diff adds a breaker. · Block if: opening and closing are not logged or exposed as a metric or status field.
- [ ] **Does a stated reset time win over the timer?** · Applies when: the protected dependency returns 429 or 503 with `Retry-After`, or a quota reset time. · Block if: the breaker ignores the stated time and probes on its own fixed timer.

## In the factory
- `factory/intake/webhook_adapter.py:479-492`: a round that hits the Claude plan's usage limit pauses until the reset time the error states, then tries once more. With one worker (`RUN_EXECUTOR`, `:151`), that pause holds the whole queue. It is a circuit breaker in all but name, opened by a failure that states its own reset time. Right.
- `factory/intake/webhook_adapter.py:328`: every round starts by cloning from GitHub, so a GitHub git outage fails the run in seconds, before any plan usage. Natural fail-fast. Right.
- A GitHub failure during the push loses that build, and one at PR creation or check polling leaves the branch pushed but the run `error`. The fix is the retry gap in 012-retries.md, not a breaker.
- A dependency that is down for every run, such as a logged-out `gh`, makes each queued run build and then fail. For a serial worker the cheap guard is a dependency check before the build (see 056-health-checks.md), not a breaker.
- Not applicable at today's load: a general breaker library or per-dependency breakers. One serial worker with at most `MAX_PENDING` (5) queued runs wastes at most a few builds in an outage, and bounded retries plus the existing pause cover it.

## Proof
`python3 -I knowledge/systems/proofs/010_circuit_breaker.py`, in simulated time, at 10 requests a second: healthy 0–10 s, hung until the 2 s timeout 10–40 s, failing half its calls 40–60 s, recovered 60–80 s. The breaker opens after 5 consecutive failures, for 5 s:
```
no breaker
  phase           success   calls reaching dependency   caller-seconds waiting
  healthy            100%                         100                      5.0
  hung                 0%                         300                    600.0
  half failing        50%                         200                     10.0
  recovered          100%                         200                     10.0

breaker
  phase           success   calls reaching dependency   caller-seconds waiting
  healthy            100%                         100                      5.0
  hung                 0%                          10                     20.0
  half failing        23%                          97                      4.8
  recovered           76%                         151                      7.5
```
In the outage, the breaker cut load on the dependency 30× and caller waiting 30×. In the partial outage, it halved the success rate. After recovery, it kept rejecting good calls until its window passed.

## Related
011-timeouts.md, 012-retries.md, 044-backpressure.md, 056-health-checks.md, 020-dead-letter-queues.md, 001-rate-limiting.md, 013-exponential-backoff.md, 051-feature-flags.md

## Sources
- Martin Fowler, "CircuitBreaker": https://martinfowler.com/bliki/CircuitBreaker.html
- "Circuit Breaker pattern", Azure Architecture Center: https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
- Marc Brooker, "Timeouts, retries, and backoff with jitter", Amazon Builders' Library (prefers token buckets to breakers because of modal behavior): https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
