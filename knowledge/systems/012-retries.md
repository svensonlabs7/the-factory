# 12. Retries

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
A retry repeats a failed call in the hope the failure was temporary: a dropped connection, a busy server, a brief outage. Retries turn many short blips into successes, but every retry adds load to a dependency that may already be struggling. They are safe only when the error is temporary, the operation can be repeated without a double effect, and the total number of attempts is bounded.

## When it is worth it
It is worth it when a call crosses a network to a dependency that fails briefly and independently, and the operation is idempotent: reads, pushes of a fixed commit, `PUT`-style updates. Use a small bound (two or three attempts in total) with backoff, at a single layer. Below that, skip it: a permanent error (bad input, auth, not found) never succeeds on retry, and a local call that fails deterministically only fails slower. Retry budgets and token buckets matter with many clients sharing one dependency. One factory process does not need them; a bounded attempt count is enough.

## How it fails
- **Retrying permanent errors:** a 400 or "branch already exists" is retried three times → the same failure, three times slower, three times the load.
- **Retry amplification:** each layer of a call stack retries independently → a dead dependency sees attempts multiplied per layer (3 layers × 3 attempts = 27×).
- **Unbounded retries:** a retry loop with no attempt limit or deadline → the caller never finishes, and the dependency never gets room to recover.
- **Duplicate side effects:** a non-idempotent call times out after it actually succeeded → the retry charges, creates or sends a second time.
- **Wrong kind of retry:** an infrastructure failure is treated as a work failure → the system redoes the work (or asks a person or agent to fix it) when it should only repeat the call.
- **Retrying in lockstep:** many callers retry at the same instant after an outage → a synchronized spike (see 013-exponential-backoff.md).

## Review checklist
- [ ] **Is every retry bounded?** · Applies when: the diff adds a retry loop, a `while` around a call, or a retry option. · Block if: there is no maximum attempt count and no deadline.
- [ ] **Does it retry only temporary errors?** · Applies when: the diff adds a retry. · Block if: it retries on every exception, or on errors that cannot succeed later (4xx other than 408/429, validation, auth, not found).
- [ ] **Is the retried operation safe to repeat?** · Applies when: the diff retries a call with side effects (create, send, charge, push, enqueue). · Block if: a repeat could apply the effect twice and there is no idempotency key or check (see 014-idempotency.md).
- [ ] **Is there one retrying layer?** · Applies when: the diff adds a retry around a call that itself retries (an SDK with built-in retries, a helper that retries, a caller that retries the whole operation). · Block if: two or more layers retry the same failure.
- [ ] **Does a failure that is not the work's fault avoid redoing the work?** · Applies when: the diff decides what happens after a failed check, job or review. · Block if: an infrastructure or tooling failure (crash, quota, timeout, no verdict) is handled the same way as a real negative result.

## In the factory
- `factory/intake/webhook_adapter.py:479-492`: a build round that failed on the plan's usage limit pauses until reset and reruns once. It retries one specific temporary error, bounded to one attempt, and every other failure propagates. Right.
- `factory/intake/webhook_adapter.py:358-372`: check polling treats "no checks reported" as the only error that means keep waiting, under a 20-minute deadline. Right.
- `factory/intake/webhook_adapter.py:58,511-522`: fix rounds are bounded (`MAX_RETRIES = 2`). They are new attempts with feedback, not retries of the same call.
- Gap: `factory/intake/webhook_adapter.py:313` (`_run`) never retries, so one transient GitHub error during polling or push ends the run and discards the build (see GAPS.md).
- Gap: a reviewer that crashes fails its check like a BLOCK, so the adapter redoes the work instead of rerunning the check (`qa-gate.yml:61-66`, `webhook_adapter.py:516-522`; see GAPS.md).
- Not applicable at today's load: retry budgets or token buckets. One process makes the calls, so a bounded attempt count is enough.

## Proof
`python3 -I scratchpad/mastery/012_retries.py`:
```
A  flaky db, no retry:      success 79.8%
A  flaky db, 3 attempts:    success 99.3%
B  dead db, retries at user+api+service    db calls per request: 27
B  dead db, retries at user                db calls per request: 3
C  dead db, 3 attempts, no budget: 3.00 db calls per request
C  dead db, 3 attempts, budget:    1.01 db calls per request
D  permanent error, retry everything calls per request: 3
D  permanent error, retry transient  calls per request: 1
```

## Related
011-timeouts.md, 013-exponential-backoff.md, 014-idempotency.md, 010-circuit-breakers.md, 001-rate-limiting.md

## Sources
- Marc Brooker, "Timeouts, retries, and backoff with jitter", Amazon Builders' Library: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
- "Handling Overload", Google SRE book: https://sre.google/sre-book/handling-overload/
- "Addressing Cascading Failures", Google SRE book: https://sre.google/sre-book/addressing-cascading-failures/
