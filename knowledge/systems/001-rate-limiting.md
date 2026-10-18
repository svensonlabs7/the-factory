# 1. Rate Limiting

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
Rate limiting caps how much one caller may ask of a service: requests per second, requests in flight, runs per day. Requests over the cap are refused, usually with HTTP 429 and ideally a `Retry-After`, so one caller cannot starve the others or drive up costs. The common algorithms:
- **Fixed window:** count per clock window. Simple, but it allows double the limit across a window edge.
- **Sliding log or window:** count over the last N seconds. Exact, and it costs memory per request.
- **Token bucket:** allows bursts up to the bucket size, then a steady refill rate.
- **Concurrency limit:** caps work in progress, whatever its rate. That is the right cap for expensive, long-running work.

Load shedding is a different tool: it drops work based on the whole system's state, not one caller's.

## When it is worth it
Any endpoint that is reachable by callers you do not fully control, or that starts expensive work (builds, LLM calls, emails, payments), needs a cap. Pick the cap that matches the cost: a concurrency limit for long jobs, a daily or hourly budget for spend, and a per-IP rate at the edge for floods. Authenticate before counting, so strangers cannot use up a real caller's quota. Limit state shared across servers (Redis and the like), per-endpoint tiers and adaptive limits matter with many servers and many tenants, not with one process and one caller.

## How it fails
- **No cap on expensive work:** a buggy or hostile client sends 100 triggers → 100 builds queued, the plan budget is gone, and real work waits behind them.
- **Fixed-window edge burst:** 10 requests at 0.99 s and 10 at 1.01 s all pass a "10 per second" fixed window → twice the intended load in 20 ms.
- **Counting before authenticating:** unsigned requests use up the quota → a stranger locks out the legitimate client.
- **Limiter as a single point of failure:** the limit store (Redis) is down and the limiter fails closed → every request is refused. Stripe fails open for this reason.
- **Limit set at exactly the expected rate:** a client sending exactly at the limit gets occasional false rejections from timing jitter and boundary rounding.
- **Rejections that cost too much:** logging or answering every rejected request in full during a flood → the limiter itself exhausts disk or CPU.
- **A 429 with no `Retry-After`:** clients guess when to come back (see 013-exponential-backoff.md).

## Review checklist
- [ ] **Is expensive or externally reachable work capped?** · Applies when: the diff adds an endpoint, webhook or job trigger that starts paid, slow or resource-heavy work, or is reachable from outside. · Block if: nothing limits how many such requests one caller can start, in flight or per period.
- [ ] **Does authentication come before counting?** · Applies when: the diff adds or reorders limiter and auth checks. · Block if: unauthenticated requests count toward an authenticated caller's limit.
- [ ] **Does the window allow edge bursts the cost cannot absorb?** · Applies when: the diff adds a rate limiter. · Block if: it uses a fixed window where a burst of twice the limit across the edge would exceed a hard cost or capacity bound.
- [ ] **Does a limiter failure fail open, and is that a deliberate choice?** · Applies when: the diff puts limiter state in an external store. · Block if: a store outage refuses all traffic without a deliberate decision recorded in the code.
- [ ] **Are rejections cheap?** · Applies when: the diff logs or records rejected requests. · Block if: per-rejection writes have no size or rate bound.

## In the factory
- `factory/intake/webhook_adapter.py:593-594`: `/trigger` authenticates (signature, freshness, replay) before `_check_capacity`, so unsigned requests never use a slot. Right.
- `factory/intake/webhook_adapter.py:72-73,220-232`: `MAX_PENDING` (5 in flight) is a concurrency limit that fits long builds, and `MAX_RUNS_PER_DAY` (30 per sliding 24 hours) is a spend cap on the Claude plan. Both are checked in the event loop with no `await` before the run is recorded, so two requests cannot both take the last slot. Right.
- `factory/intake/webhook_adapter.py:78,554-587` (`_log_rejection`): `rejected.jsonl` stops growing at 5 MB, and a burst of 401s or 422s raises an incident in HEARTBEAT. Rejections stay cheap. Right.
- `infra/cloudflare-tunnel/README.md:42-50`: a Cloudflare edge rule allows 5 `/trigger` requests per 10 s per IP, Access service auth sits in front of the hostname, and only `/trigger` and `/health` are routed. Floods stop at the edge before the Mac. Right, but documented rather than in code (see 104-infrastructure-as-code.md).
- `factory/intake/webhook_adapter.py:646` (`PR_CACHE_TTL`): the dashboard reuses a PR's state for 60 s, so refreshing does not turn into GitHub calls. Right.
- Gap already logged: the 429 has no `Retry-After` (013-exponential-backoff.md).
- Not applicable at today's load: shared limiter stores, per-tenant tiers and load shedders. There is one process and one caller.

## Proof
`pytest -s scratchpad/mastery/001_rate_limiting.py` (A uses the real adapter through `tests/test_adapter.py`'s fixture):
```
A  6 valid triggers with 25 unsigned ones in between, MAX_PENDING=5: [202, 202, 202, 202, 202, 429]
A  4 valid triggers, MAX_RUNS_PER_DAY=3: [202, 202, 202, 429]
B  limit 10/s     20 sent in 20 ms across a window edge   100 sent evenly over 10 s
B  fixed window                      20 allowed                           100 allowed
B  sliding log                       10 allowed                            98 allowed
B  token bucket                      10 allowed                           100 allowed
```
The sliding log refusing 2 of 100 evenly spaced requests is floating-point rounding at the window edge, which shows why a limit set at exactly the expected rate misfires.

## Related
013-exponential-backoff.md, 044-backpressure.md, 075-ddos-protection.md, 074-waf.md, 012-retries.md, 101-webhooks.md, 010-circuit-breakers.md

## Sources
- Paul Tarjan, "Scaling your API with rate limiters", Stripe engineering blog: https://stripe.com/blog/rate-limiters
- RFC 6585, section 4 "429 Too Many Requests" and section 7.2: https://www.rfc-editor.org/rfc/rfc6585#section-4
