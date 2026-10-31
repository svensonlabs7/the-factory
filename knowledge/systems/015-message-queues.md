# 15. Message Queues

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

Triggers: lines `RUN_EXECUTOR|\.submit\(|Queue\(|IN_FLIGHT|_recover\(|(?i:redeliver|dequeue)`

## What it is
A message queue sits between a producer and a consumer. The producer hands work over and returns at once; the consumer takes it when it has capacity. This decouples their speed and availability: bursts wait in the queue instead of overloading the consumer, and the producer keeps accepting work while the consumer is down.

What makes a queue reliable is when it forgets a message:
- **At-most-once:** the message is removed on delivery. A consumer crash loses it.
- **At-least-once:** the message is removed only when the consumer acknowledges it after processing. A crash makes it reappear. SQS calls the hidden period the visibility timeout, 30 s by default and at most 12 h. So duplicates are possible, and consumers must be idempotent.
- **Exactly-once** is at-least-once delivery plus idempotent processing. It is not a property of the transport.

Durable queues persist messages so they survive a broker restart. Messages that keep failing go to a dead-letter queue after a set number of receives (see 020-dead-letter-queues.md).

## When it is worth it
A queue is worth it when producers and consumers run at different speeds or have different availability, when work takes longer than a request should, or when bursts must be absorbed. A separate broker (SQS, RabbitMQ, Kafka) is worth it when several processes or machines produce or consume, or when the queue must outlive any one of them. For one process with a handful of jobs, an in-process worker plus a durable record of each job (a row, a file) is a queue already. It needs only the acknowledge-after-processing discipline, not a broker.

## How it fails
- **Acknowledged on delivery:** the message is removed before it is processed → a consumer crash loses it (at-most-once by accident).
- **In-memory only:** the queue lives in process memory → a restart, crash or deploy drops everything waiting.
- **Visibility timeout shorter than the work:** a slow consumer's message reappears and a second consumer processes it too → duplicate side effects.
- **Non-idempotent consumer on an at-least-once queue:** a redelivery charges twice, sends twice, opens two PRs.
- **Poison message:** one message that always fails is redelivered forever and blocks or burns the consumer, unless a DLQ catches it.
- **Unbounded queue:** producers outrun consumers with no backpressure → latency grows without limit and memory fills (044-backpressure.md).

## Review checklist
- [ ] **Is a message removed only after it is processed?** · Applies when: the diff adds or changes a consumer of a queue, job table or work directory. · Block if: the message or job is deleted, marked done or acknowledged before its processing has finished.
- [ ] **Does waiting work survive a restart?** · Applies when: the diff adds a queue or work pool, or changes how accepted work is stored or recovered after a restart. · Block if: work acknowledged to the producer lives only in memory, or the recovery it adds or changes discards accepted work that never started.
- [ ] **Is redelivery safe?** · Applies when: the diff consumes from an at-least-once queue or redelivers work after a crash. · Block if: processing the same message twice repeats a side effect (a payment, a push, a PR) with no idempotency key or check.
- [ ] **Is processing time bounded below the redelivery timeout?** · Applies when: the diff sets a visibility timeout or lease, or changes how long a consumer works on one message. · Block if: the work can outlast the timeout with no heartbeat or extension.
- [ ] **Does a failing message stop circulating?** · Applies when: the diff adds a consumer with retries. · Block if: there is no maximum receive count or DLQ.
- [ ] **Is a broker justified?** · Applies when: the diff adds a message broker or queue service. · Block if: one process produces and consumes, and a durable record plus an in-process worker would do.

## In the factory
- The adapter's queue is `RUN_EXECUTOR` (`factory/intake/webhook_adapter.py:151`, one worker, FIFO) plus a durable `queued` record per run (`:608`), which holds the task and branch.
  - Producers get backpressure: `MAX_PENDING = 5` and `MAX_RUNS_PER_DAY = 30` (`:72-73`) turn excess `/trigger` calls into 429s.
  - Started runs are closed out as `error` on restart instead of being redelivered. That is right, because a started run may already have pushed or opened a PR, and the build is not idempotent (014-idempotency.md).
- Gap (low): accepted runs that never started are lost on a restart.
  - The work queue is in memory, and `_recover` (`:715-732`) closes every `queued` run as `error` ("the service restarted during the run"), although nothing ran and its task and branch are on disk.
  - The proof shows that putting them back on the queue completes them.
  - `/trigger` already answered 202 for them, and no sender retries a 202 (see GAPS.md).
- `RUN_EXECUTOR` has no visibility timeout. Each run is bounded by the agent timeout and the checks deadline (011-timeouts.md).
- Not applicable at today's load: a message broker, multiple consumers, visibility timeouts and leases. There is one producer endpoint, one worker, at most 5 waiting runs and 30 a day.

## Proof
`pytest -s knowledge/systems/proofs/015_queues.py` (Python 3.11): the real adapter through `tests/test_adapter.py`'s fixture, with a fake agent that sleeps 1 s. A crash is simulated by discarding the in-memory queue and re-importing the module:
```
A  at the crash: {'93d47489': 'running', 'fd09141c': 'queued', '483289f7': 'queued'}
A  after restart: {'93d47489': ('error', 'started'), 'fd09141c': ('error', 'never started'), '483289f7': ('error', 'never started')}
B  never-started runs put back on the queue: [('63e11774', 'completed'), ('027e5aaf', 'completed')]
```
In B, the scratch file stands in for a `_recover` that tells never-started runs from started ones. The adapter's own `_build_prompt` and `_run_agent` finish them from their records on disk.

## Related
016-pub-sub.md, 017-event-driven-architecture.md, 020-dead-letter-queues.md, 014-idempotency.md, 044-backpressure.md, 054-rolling-deployments.md, 011-timeouts.md

## Sources
- "Amazon SQS visibility timeout", Amazon SQS Developer Guide: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- "Reliability Guide", RabbitMQ documentation: https://www.rabbitmq.com/docs/reliability
