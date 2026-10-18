# 101. Webhooks

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
A webhook is an HTTP request one system sends another when something happens, so the receiver does not have to poll. The receiver's URL is public, so it must prove each request is genuine, fresh and new:
- **Genuine:** an HMAC signature over the raw body with a shared secret, compared in constant time.
- **Fresh:** a signed timestamp within a short tolerance.
- **New:** a unique delivery id remembered for at least that tolerance, so a replay or a retry is recognized.

Senders retry on any non-2xx or timeout, so a receiver should answer fast (2xx within seconds), do the real work in the background, and treat a repeat of a delivery id as the same event. The Standard Webhooks spec signs `id.timestamp.body` and puts the three in `webhook-id`, `webhook-timestamp` and `webhook-signature` headers.

## When it is worth it
Receiving: whenever another system must start work here, and polling would be slow or wasteful. The checks above are the minimum for any public receiver, at any scale. Sending: when consumers need to react to events. Then you also own retries with backoff, a delivery log and endpoint disabling. That sender machinery is over-engineering until someone actually subscribes.

## How it fails
- **Unsigned or wrongly verified:** no signature, a signature over a re-serialized body instead of the raw bytes, or a `==` comparison → forged requests start work, or timing leaks the signature.
- **No freshness:** a captured request is replayed days later → the work runs again.
- **No delivery id:** the sender retries after a timeout → the event is processed twice (see 014-idempotency.md).
- **Slow response:** the receiver does the work before answering → the sender times out and retries, and duplicates pile up.
- **Unbounded payload:** a huge body is accepted → memory spikes, or it fails later somewhere the error is confusing (argv limits, database column sizes).
- **Rotation outage:** changing the secret breaks every in-flight sender, because the receiver accepts only one secret.

## Review checklist
- [ ] **Is every inbound webhook verified?** · Applies when: the diff adds or changes an endpoint that another system calls. · Block if: it acts before checking an HMAC (or asymmetric) signature over the raw body with a constant-time compare.
- [ ] **Is it fresh and new?** · Applies when: the diff adds a webhook receiver. · Block if: there is no signed-timestamp tolerance, or no memory of seen deliveries for at least that tolerance.
- [ ] **Does a retry of the same event act once?** · Applies when: the receiver starts work with side effects. · Block if: a sender retry (same event, new attempt) can start the work twice (see 014-idempotency.md).
- [ ] **Does it answer fast and work in the background?** · Applies when: the handler does more than validate and enqueue. · Block if: slow work (builds, external calls, LLM calls) runs before the 2xx is returned.
- [ ] **Is the payload bounded at the door?** · Applies when: the diff adds a receiver or a free-text field to one. · Block if: body size or field lengths are unbounded, so oversized input is accepted and fails later.
- [ ] **Can the secret rotate without an outage?** · Applies when: the diff adds a signing secret. · Block if: only one secret can be valid at a time.

## In the factory
- `factory/intake/webhook_adapter.py:190-196` (`_verify_signature`): HMAC-SHA256 over `"<timestamp>." + raw body`, with `hmac.compare_digest`, under the current or previous secret (`WEBHOOK_SECRETS`, `:49`). Right.
- `factory/intake/webhook_adapter.py:235-245` (`_authenticate`), `:74`: a 5-minute timestamp window, plus an atomic replay record per signature (`_replayed`). Right.
- `factory/intake/webhook_adapter.py:44-47`: the service refuses to start without a secret. Right.
- `factory/intake/webhook_adapter.py:608-618`: `/trigger` records the run, submits it to the worker and answers `202` straight away (2 ms in the proof). Right.
- `factory/intake/webhook_adapter.py:180-183` (`TriggerPayload`): `branch` must match `^factory/...`, so a caller can never target `main`. Right.
- `infra/cloudflare-tunnel/README.md:42-50`: Cloudflare Access service auth, an edge rate limit, and only `/trigger` and `/health` routed on the intake hostname. Defense beyond the signature. Right.
- Gap already logged: no delivery id, so a sender retry starts a second run (014-idempotency.md).
- Gap: `task` has no length limit. A 2 MB task is accepted with 202, then fails at spawn with `Argument list too long` (see GAPS.md).
- Not applicable at today's load: sending webhooks. Grok Bot polls `/heartbeat` instead.

## Proof
`pytest -s scratchpad/mastery/101_webhooks.py`, against the real adapter through `tests/test_adapter.py`'s fixture:
```
1  tampered body: {'detail': 'Invalid signature'}
2  signed 400 s ago: {'detail': 'Stale request'}
4  answered 202 in 2 ms; the run finished 3.9 s later as completed
5  2 MB task: 202 accepted, then status='error' error="[Errno 7] Argument list too long: '.../fake-agent.sh'"
3  signed with the previous secret during rotation: 202
```
`getconf ARG_MAX` is 1048576 on this Mac. The production agent command passes the prompt as an argument the same way, so it fails at the same limit.

## Related
014-idempotency.md, 001-rate-limiting.md, 011-timeouts.md, 067-secrets-management.md, 013-exponential-backoff.md, 012-retries.md, 077-csrf.md

## Sources
- "Best practices for using webhooks", GitHub Docs: https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
- Standard Webhooks specification: https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md
