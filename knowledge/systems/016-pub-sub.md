# 16. Pub/Sub

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

## What it is
Publish/subscribe decouples who emits an event from who reacts to it. Publishers send to a topic or channel without knowing the subscribers, and every subscriber gets its own copy (fan-out). A queue is different: each message goes to one consumer.

Delivery guarantees vary widely, and they are the whole design question:
- **Redis Pub/Sub** is at-most-once. If a subscriber cannot handle a message, "the message is forever lost." Nothing is stored.
- **Durable systems** (Redis Streams, Kafka, Google Pub/Sub) keep messages and track each subscriber's position (an offset or acknowledgements). A subscriber that was away catches up, with at-least-once delivery and therefore duplicates. A new Google Pub/Sub subscription only receives messages published after it was created.
- **Webhooks** are push pub/sub over HTTP. GitHub "does not automatically redeliver failed deliveries."

The deeper choice is edge- versus level-triggered:
- **Edge-triggered:** react to events, and a missed event leaves you wrong.
- **Level-triggered:** read the current state, poll or reconcile, and a missed change is corrected on the next read, at the cost of latency and repeated reads.

## When it is worth it
Pub/sub is worth it when several independent consumers react to the same events, when producers must not know or wait for consumers, or when polling is too slow or too costly at scale. A durable log is needed whenever a consumer must not miss events. A fire-and-forget channel is fine only for data whose loss does not matter (presence, live cursors). When there are few readers and modest latency needs, polling the current state is simpler, self-healing and enough. Push systems need a reconciliation poll anyway to cover missed deliveries.

## How it fails
- **Fire-and-forget for data that matters:** a subscriber disconnected during a deploy or a blip misses events → its view is wrong until something else corrects it.
- **Edge-triggered state with no reconciliation:** a missed "completed" event leaves the watcher on "pending" forever.
- **Duplicates on catch-up:** durable delivery is at-least-once → a subscriber that is not idempotent applies an event twice.
- **Subscription created late:** events published before the subscription existed are not delivered.
- **Slow subscriber:** with push fan-out, one slow consumer backs up or drops. With a durable log, its lag grows until retention expires and it loses data anyway.
- **Hidden coupling:** "decoupled" consumers depend on an event's shape with no contract (082-schema-versioning.md).

## Review checklist
- [ ] **Can a subscriber miss an event that matters?** · Applies when: the diff publishes or consumes events (a channel, webhook, callback or event bus). · Block if: delivery is at-most-once (fire-and-forget, a webhook without redelivery) for an event whose loss leaves state wrong, and there is no durable log or reconciliation.
- [ ] **Is state rebuilt from current truth, not only from events?** · Applies when: the diff tracks external state (PR, job or deploy status) from incoming events. · Block if: a missed or out-of-order event leaves the state wrong, with no periodic poll or reconcile against the source.
- [ ] **Are subscribers idempotent?** · Applies when: the diff consumes from a durable, at-least-once topic. · Block if: a redelivered event repeats a side effect.
- [ ] **Is the event's shape a contract?** · Applies when: the diff changes an event or webhook payload that other components consume. · Block if: it renames or retypes a field consumers read (see 102-api-versioning.md).
- [ ] **Is push justified over polling?** · Applies when: the diff replaces polling with webhooks or a broker. · Block if: there are few readers, polling latency is acceptable, and the change adds a public endpoint or broker without a reconciliation path.

## In the factory
- The factory has no pub/sub. Every observer polls the current state, which is level-triggered. Right at this scale:
  - `factory/intake/webhook_adapter.py:352-370` (`_gate_results`) polls `gh pr checks` every 15 s (`CHECKS_POLL`, `:64`) instead of subscribing to GitHub's `check_suite` webhooks;
  - the dashboard polls `/command/data` every 15 s (`factory/intake/command.html:128`);
  - Grok Bot is meant to poll `/heartbeat`. HEARTBEAT is in effect the factory's one "topic", fanned out by polling.
- The cost of polling is small. In run 920d7293 the adapter saw the gate result 16 s after the last job ended, about 3% of a 492 s run (060-distributed-tracing.md), at about two `gh` calls per poll.
- Webhooks would save at most 15 s per run. They would add a public endpoint, signature checks, and a reconciliation poll for the deliveries GitHub does not retry.
- Not applicable at today's load: brokers, durable topics and webhook subscriptions.

## Proof
`python3 -I scratchpad/mastery/016_pubsub.py` uses real sockets. A publisher fans each event out to the subscribers connected at that moment, as Redis `PUBLISH` does. One subscriber is disconnected for two events:
```
A  fire-and-forget: steady subscriber got 4/4; flaky subscriber got 2/4 -> ['checks: pending', 'pr: merged']
B  durable log + offset: flaky subscriber reads from offset 1 on reconnect -> ['checks: running', 'checks: completed (pass)', 'pr: merged']
C  edge-triggered checks state from events: 'checks: pending'; level-triggered poll of current state: 'checks: completed (pass)'
```
B also shows at-least-once duplication: `pr: merged` arrives twice, once live and once on catch-up. C is why `_gate_results` polls.

## Related
015-message-queues.md, 017-event-driven-architecture.md, 020-dead-letter-queues.md, 060-distributed-tracing.md, 102-api-versioning.md, 014-idempotency.md

## Sources
- "Redis Pub/sub" (Delivery semantics), Redis documentation: https://redis.io/docs/latest/develop/pubsub/
- "Subscription overview", Google Cloud Pub/Sub documentation: https://docs.cloud.google.com/pubsub/docs/subscription-overview
- "Handling failed webhook deliveries", GitHub documentation: https://docs.github.com/en/webhooks/using-webhooks/handling-failed-webhook-deliveries
