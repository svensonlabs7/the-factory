# 20. Dead Letter Queues

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
A dead letter queue (DLQ) is where work goes after it has failed too many times to keep retrying. Without one, a poison message, meaning one that always fails, is retried forever. It wastes capacity and, in an ordered queue, blocks everything behind it. With one, the message is moved aside after a set number of attempts (`maxReceiveCount` in SQS), the rest of the queue flows, someone is alerted, and after the bug is fixed the dead messages are redriven, that is, sent back through the normal path. The idea applies to any system that retries work, not just message brokers: a job table with a `failed` status and its reason is a DLQ.

## When it is worth it
It is worth it for any automatic retry of queued or background work, because some failures are permanent and will never succeed on retry. The essentials are a bounded number of attempts, a durable place for the dead item with its reason, an alarm on any arrival, and a way to redrive. Do not use one where order is the point, such as a sequence of edits where skipping one corrupts the ones after it; those must stop and wait. A separate broker queue with redrive policies is over-engineering for a single worker whose failed jobs are already recorded with a terminal status.

## How it fails
- **No DLQ, infinite redelivery:** a poison message is redelivered forever → in a FIFO queue nothing behind it is processed, and in any queue it burns capacity.
- **Crash-loop on restart:** a job that crashes the worker is requeued on restart → the worker crashes again, forever.
- **Silent DLQ:** messages land in the DLQ and no one is told → the work is lost in practice, though not on disk.
- **Alarm overwritten:** the failure signal is a "latest status" field → the next success overwrites it, and the failure is never seen.
- **Threshold of 1:** one transient blip sends good work to the DLQ.
- **DLQ retention shorter than the source:** dead messages expire before anyone looks.
- **Redrive without a fix:** the same messages fail again and return to the DLQ, taking capacity again on the way.

## Review checklist
- [ ] **Does automatic retry of queued work end somewhere?** · Applies when: the diff adds a retry, requeue or redelivery of jobs, messages or runs. · Block if: there is no attempt limit after which the item is parked with its error.
- [ ] **Is a parked item kept with enough to act on?** · Applies when: the diff adds a terminal failure state or a DLQ. · Block if: the item's input, failure reason and attempt count are not all kept, at least as long as the original work is.
- [ ] **Does a dead item raise a signal that the next success cannot erase?** · Applies when: the diff adds or changes how failures are reported. · Block if: the only signal is a "latest status" field that a later success overwrites, with no count of unresolved dead items and no alert.
- [ ] **Can a restart requeue the job that crashed it?** · Applies when: the diff adds startup recovery of in-flight work. · Block if: in-flight work is requeued automatically with no attempt count, so a crashing job crash-loops the service.
- [ ] **Is there a way to redrive?** · Applies when: the diff adds a DLQ or terminal failure state. · Block if: the only way to retry a dead item is to rebuild it by hand from logs.

## In the factory
- `factory/intake/webhook_adapter.py:397-414` (`_finish`), `:523-530`: every run ends in a terminal status (`failed`, `error`, `blocked`, `timeout`). Its task, reason, PR, log and action log are kept, and nothing retries it automatically. Retries are bounded before that point: fix rounds by `MAX_RETRIES`, usage-limit reruns to one. This is the factory's DLQ. Right.
- `factory/intake/webhook_adapter.py:715-732` (`_recover`): a run that was in flight when the service died is parked as `error`, not requeued, so a run that crashes the adapter cannot crash-loop it. Right.
- `factory/intake/webhook_adapter.py:79`: parked runs are kept 30 days (`RUN_RETENTION_DAYS`). Right.
- `.factory-logs/rejected.jsonl` (`_log_rejection`, see 001-rate-limiting.md) is the dead-letter record for invalid inbound requests, without bodies or signatures. Right.
- Redrive is manual: copy the task from the run's `meta.json` and sign a new trigger. Acceptable for one operator, but every redrive also needs the signing format right.
- Gap: HEARTBEAT reports only the latest run, so a failed run is erased by the next success, and no count of unresolved dead runs exists (see GAPS.md).
- Not applicable at today's load: a broker DLQ, redrive policies or DLQ metrics. One worker and a status field do the job.

## Proof
`pytest -s knowledge/systems/proofs/020_dlq.py`. A is a 20-message FIFO simulation where message 2 always fails. B uses the real adapter through `tests/test_adapter.py`'s fixture:
```
A  no DLQ:            processed 2/19 good, 200 receives used, 18 still queued
A  maxReceiveCount=3: processed 19/19 good, 22 receives used, DLQ=[2]  -> alarm: 1 dead message
A  redrive, no fix:   processed [], back in DLQ [2]
A  redrive after fix: processed [2], back in DLQ []
B  run 79e81f27: failed -> heartbeat pipeline_status='failed'
B  run 56481ae8: completed -> heartbeat pipeline_status='idle' blocking_reason='—'; the failed run is still on disk: failed
B  in-flight run after restart: status='error' error='the service restarted during the run' (parked, not requeued)
```

## Related
012-retries.md, 044-backpressure.md, 014-idempotency.md, 062-alerts.md, 015-message-queues.md, 010-circuit-breakers.md, 058-monitoring.md

## Sources
- "Using dead-letter queues in Amazon SQS", AWS documentation: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html
- David Yanacek, "Avoiding insurmountable queue backlogs", Amazon Builders' Library (DLQ alarms and redrive): https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs
- Gregor Hohpe and Bobby Woolf, "Dead Letter Channel", Enterprise Integration Patterns: https://www.enterpriseintegrationpatterns.com/patterns/messaging/DeadLetterChannel.html
