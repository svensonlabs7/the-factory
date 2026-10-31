# 13. Exponential Backoff

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)backoff|jitter|retry.?after|\*\* ?attempt|2 ?\*\* `

## What it is
Backoff is how long a caller waits before retrying. Exponential backoff doubles the wait after each failure, up to a cap (2 ms, 4, 8 ... 1 s), so a struggling dependency gets fewer calls the longer it struggles. Jitter adds randomness to each wait. Without jitter, callers that failed together retry together and keep colliding. If the server says when to come back (`Retry-After`, a rate-limit reset time, "resets 5:40am"), that time beats any formula.

Formulas, with `base`, `cap` and attempt `n`:
- exponential: `min(cap, base * 2^n)`
- full jitter: `random(0, min(cap, base * 2^n))`
- equal jitter: `t/2 + random(0, t/2)`, where `t = min(cap, base * 2^n)`
- decorrelated: `min(cap, random(base, previous * 3))`

## When it is worth it
It is worth it for any retry against a shared or remote dependency, and for many clients that can fail together (after an outage, a deploy, a rate-limit reset). Use full jitter by default. A single caller retrying one call two or three times only needs a short fixed delay, or the server's reset time; formula tuning there is wasted effort. Polling is not backoff: poll on a fixed schedule as slowly as the use allows, and honor any poll-interval or reset the server sends.

## How it fails
- **No backoff:** immediate retries hammer a dependency that is already failing → it cannot recover, and in contention nobody makes progress.
- **Backoff without jitter:** clients that started together double their waits in lockstep → they collide again on every attempt, in bursts with idle gaps between.
- **No cap:** the doubling keeps growing → a client that failed ten times waits minutes or hours for no reason.
- **Ignoring the server's answer:** a client backs off by formula while the server said `Retry-After: 60` or gave a reset time → too early it is rejected again (and risks a ban), too late it wastes time.
- **A server that never says when:** it answers 429 or 503 without `Retry-After` → every client guesses, and the guesses arrive together.

## Review checklist
- [ ] **Does each retry wait before trying again?** · Applies when: the diff adds a retry against a remote or shared dependency. · Block if: it retries immediately in a loop with no delay.
- [ ] **Is the backoff capped and jittered?** · Applies when: the diff adds exponential backoff, or a retry that many clients could run at once. · Block if: the wait has no cap, or many clients use the same deterministic delays with no jitter.
- [ ] **Does it honor the server's own wait?** · Applies when: the diff retries a call whose responses can carry `Retry-After`, `x-ratelimit-reset` or a stated reset time. · Block if: that value is ignored in favor of a formula.
- [ ] **Does our own 429 or 503 say when to retry?** · Applies when: the diff adds or changes a 429 or 503 response. · Block if: it has no `Retry-After` and the server knows, or can estimate, when capacity returns.
- [ ] **Does polling stay on a fixed, documented interval?** · Applies when: the diff adds a polling loop. · Block if: the loop polls with no delay, or ignores a poll interval the API sends.

## In the factory
- `factory/intake/webhook_adapter.py:460-476` (`_usage_limit_wait`): a usage-limit failure waits until the reset time the log states, falls back to 30 minutes, and is capped at 5 hours. It honors the server's own wait, and one caller needs no jitter. Right.
- `factory/intake/webhook_adapter.py:64,358-372`: check polling runs every 15 s on a fixed schedule under a 20-minute deadline, as GitHub recommends. That is about 480 calls an hour, far below the 5,000-an-hour primary limit. Right.
- `factory/intake/webhook_adapter.py:313`: `git` and `gh` calls are not retried at all (see 012-retries.md). When that gap is fixed, honor `retry-after` and `x-ratelimit-reset`, and wait at least a minute on GitHub's secondary rate limit.
- Gap: `factory/intake/webhook_adapter.py:232` answers `429 Too many runs` with no `Retry-After` (see GAPS.md).
- Not applicable at today's load: jitter tuning and decorrelated backoff. One process makes every outbound call.

## Proof
`python3 -I knowledge/systems/proofs/013_backoff.py`, with 50 clients contending for an exclusive write in 1 ms slots, base 2 ms, cap 1 s, median of 5 seeds:
```
strategy          attempts   finished in
no backoff         6000050never (50 stuck)
exponential           6400never (50 stuck)
full jitter            383        0.30 s
equal jitter           377        0.44 s
decorrelated           415        0.38 s
```
The model has no network variance, which is the worst case for plain exponential backoff: all 50 clients stay in lockstep forever. Brooker's simulation had network variance, and plain exponential backoff was still the slowest strategy by far.

## Related
012-retries.md, 011-timeouts.md, 001-rate-limiting.md, 044-backpressure.md, 010-circuit-breakers.md, 101-webhooks.md

## Sources
- Marc Brooker, "Exponential Backoff And Jitter", AWS Architecture Blog: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- "Best practices for using the REST API", GitHub Docs: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- Marc Brooker, "Timeouts, retries, and backoff with jitter", Amazon Builders' Library: https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
