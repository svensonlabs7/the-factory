# 14. Idempotency

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
An operation is idempotent when doing it twice has the same effect as doing it once. That matters because a caller often cannot know whether its request worked: the response can be lost after the server acted. Reads, setting a value, pushing a fixed commit and deleting by id are idempotent by nature. Creating, sending, charging and enqueueing are not, so they need an idempotency key: the client picks a unique key per intended action, and the server records it with the outcome and returns that same outcome for any repeat. The same idea applies to startup and maintenance steps: a step that runs again after a crash should converge on the same end state.

## When it is worth it
It is worth it for any operation with a side effect that a client, a queue or a restart may repeat: creating runs or resources, sending messages, charging, enqueueing, and any webhook receiver whose sender retries. Keep it simple at small scale: a file or row keyed by the idempotency key, created atomically, kept for at least the client's retry window (Stripe keeps keys for 24 hours). Reads and pure functions need nothing. Hashing request parameters into a key is wrong, because two identical requests can be meant as two actions.

## How it fails
- **Lost response, duplicate effect:** the server creates the thing, the response is lost, and the client retries → two runs, two PRs, two charges.
- **Replay protection mistaken for idempotency:** a repeat is rejected as a replay or "already exists" → the client cannot tell whether its own request succeeded, or what it created.
- **Check-then-write race:** two copies of a request both see "key not found" before either records it → both act.
- **Key without parameters:** a client reuses a key for a different request → the server silently returns the old result for a new intent.
- **Non-convergent restart:** a crash leaves half-done state (a running process, a directory, a lock) → the next start fails on it, or leaves it running unsupervised.

## Review checklist
- [ ] **Can a repeat of this create, send or charge happen twice?** · Applies when: the diff adds an endpoint, job or handler with a side effect that a client, a queue, a webhook sender or a restart may repeat. · Block if: a repeat performs the effect again and there is no idempotency key, natural unique key, or existence check.
- [ ] **Does a repeat get the original answer?** · Applies when: the diff adds idempotency or duplicate detection. · Block if: a repeat gets an error ("already exists", "replayed") instead of the first request's result.
- [ ] **Is the key recorded atomically with the action?** · Applies when: the diff stores an idempotency key or a "done" marker. · Block if: it checks for the key, then writes it in a separate step that a concurrent request can slip between.
- [ ] **Is a reused key with different parameters rejected?** · Applies when: the diff accepts client-chosen idempotency keys. · Block if: the stored parameters are not compared, so a different request silently gets the old result.
- [ ] **Does startup converge after a crash at any point?** · Applies when: the diff adds a startup, recovery or setup step, or state that outlives a process (files, containers, child processes, locks). · Block if: running it twice fails, or a crash leaves state that the next start neither cleans up nor adopts.

## In the factory
- `factory/build/egress.sh:10-31`: create-if-missing for the network, recreate the proxy only when its config hash changes, flush and re-add the firewall chain, and check before inserting the jump rule. Running it every round converges on the same state. Right.
- `factory/intake/webhook_adapter.py:199-213` (`_replayed`): an atomic `touch(exist_ok=False)` record per signature. Right for replay protection, and the same atomic-create pattern an idempotency key store needs.
- `factory/intake/webhook_adapter.py:350`: pushing a fixed sha to `factory/<run_id>` is idempotent: a repeat is a no-op.
- `factory/intake/webhook_adapter.py:604-605`: each run gets a fresh id and branch, so leftover state from one run never collides with the next.
- `factory/intake/webhook_adapter.py:715-732` (`_recover`): on start, every in-flight run is closed as `error`. Right, but incomplete (gap below).
- Gap: `/trigger` (`:588`) has no idempotency key. A client retry creates a duplicate run, and an exact resend is rejected as a replay (see GAPS.md).
- Gap: `_recover` does not stop the agent process group or container of a run that was in flight when the adapter died (see GAPS.md).
- Not applicable at today's load: a shared idempotency store or key expiry service. One process and one directory are enough.

## Proof
`pytest -s scratchpad/mastery/014_idempotency.py` (A and B use the real adapter through `tests/test_adapter.py`'s fixture):
```
A  same task retried: 202 run 813641c0, 202 run b1a114d1 -> two runs for one request
B  exact resend: 202 run 961084f1, then 401 {'detail': 'Replayed request'}
C  first:          (202, {'run_id': 'run1'})
C  retry same key: (200, {'run_id': 'run1'})
C  same key, new task: (422, {'detail': 'idempotency key reused with different parameters'})
C  runs created: ['run1']
D  5 concurrent requests, one key, check-then-write: runs created 5
D  5 concurrent requests, one key, atomic create  : runs created 1
```

## Related
012-retries.md, 101-webhooks.md, 039-race-conditions.md, 020-dead-letter-queues.md, 015-message-queues.md

## Sources
- Malcolm Featonby, "Making retries safe with idempotent APIs", Amazon Builders' Library: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
- "Idempotent requests", Stripe API reference: https://docs.stripe.com/api/idempotent_requests
- pstack principle "Make Operations Idempotent": `.claude/skills/principle-make-operations-idempotent/SKILL.md`
