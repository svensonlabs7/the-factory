# 44. Backpressure

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
Backpressure is how a slow consumer tells a fast producer to slow down. When work arrives faster than it can be done, something has to give. The producer is blocked or refused (backpressure), the excess is dropped (load shedding), or an unbounded queue grows until memory, disk or latency runs out. A queue does not fix overload: it absorbs short bursts, and under sustained overload it only delays the failure and makes it bigger, because every queued item waits behind everything ahead of it. Operating systems apply backpressure all the time: a full pipe or socket buffer blocks the writer until the reader catches up.

## When it is worth it
It is needed wherever work is queued or buffered between a producer and a consumer that can fall behind: job queues, worker pools, streams, pipes to child processes, request handlers that spawn background work. The minimum is a bound on every queue, with a deliberate choice at the bound (block the producer, or refuse with 429 or 503), plus a visible depth or age. Priority lanes, LIFO drain during recovery, per-tenant fairness and shuffle sharding are for many tenants sharing a queue at scale. A single-tenant queue capped at a handful of items needs none of them.

## How it fails
- **Unbounded queue:** producers outpace the consumer → the queue grows without limit, every item waits longer than the last, and memory or disk runs out.
- **Backlog outlives the spike:** the overload ends but the queue stays deep → latency stays high long after, and stale work runs first.
- **Hidden overload:** only errors are monitored and the queue never errors → nobody sees the growing backlog until items are hours old.
- **Pipe deadlock:** a parent starts a child with `stdout=PIPE` and waits for it to exit without reading → the child fills the pipe buffer and blocks forever, and so does the parent.
- **Unbounded fan-out per request:** each request starts its own threads or tasks with no global cap → concurrency multiplies with load (Little's Law: in flight = arrival rate × latency).

## Review checklist
- [ ] **Is every new queue or buffer bounded?** · Applies when: the diff adds a queue, a list used as a queue, an executor's work queue, a channel, or an in-memory buffer between producer and consumer. · Block if: nothing limits its size.
- [ ] **Is there a deliberate choice at the bound?** · Applies when: the diff adds a bounded queue or admission check. · Block if: a full queue silently drops work, or the choice between blocking and refusing is not explicit and reported (a 429 or 503, an error, a counter).
- [ ] **Is the backlog visible?** · Applies when: the diff adds a queue that can grow under load. · Block if: neither its depth nor the age of its oldest item is exposed (status, metric, heartbeat).
- [ ] **Is a child process's output drained?** · Applies when: the diff starts a subprocess with `stdout` or `stderr=PIPE`. · Block if: the code waits for the process to exit (`wait()`) without reading its pipes. Use `communicate()`, `run(capture_output=True)`, or send the output to a file.
- [ ] **Is fan-out capped across requests?** · Applies when: the diff starts threads, tasks or subprocesses per request. · Block if: the per-request count has no global ceiling and the endpoint is reachable by more than one trusted caller.

## In the factory
- `factory/intake/webhook_adapter.py:151,72,227-232`: one worker (`RUN_EXECUTOR`) and admission control: at most `MAX_PENDING` (5) runs queued, running or in QA, and a 429 beyond that. It is a bounded queue that sheds at the door and pushes back on the producer. Right.
- `factory/intake/webhook_adapter.py:430-431`: the agent's output goes to the run's log file (`stdout=lf`), not a pipe, so a chatty agent can never block on a full buffer. Right.
- `factory/intake/webhook_adapter.py:316`: `git` and `gh` calls use `subprocess.run(capture_output=True)`, which reads both pipes while waiting. Right.
- `factory/intake/webhook_adapter.py:691-712` (`/command/data`): the dashboard shows live `pending` and `runs_24h` against their limits. Right.
- Gap: HEARTBEAT's `intake_queue_depth` is never written, so `/heartbeat` always reports 0 (see GAPS.md).
- Acceptable at today's load: queued runs carry no age limit. The worst-case wait is several hours (5 runs × up to 3 rounds, plus usage-limit pauses), and a feature request built a few hours late is still useful.
- Not applicable at today's load: priority lanes, per-tenant fairness and LIFO recovery. There is one caller and a queue of at most 5.

## Proof
`python3 -I scratchpad/mastery/044_backpressure.py`. A is simulated time: 12 jobs/s arrive for 60 s, then 8/s; one consumer does 10/s. B is a real OS pipe:
```
A  queue                  peak depth  max wait  p99 wait  rejected  last job done
A  unbounded                     121     10.0s     11.8s         0           180s
A  bounded 20, reject             20      2.0s      2.0s       101           180s
A  bounded 20, block              20      2.0s      2.0s         0           180s
B  wait() without reading a 1 MB stdout pipe: still blocked after 3s (child stuck on a full pipe)
B  communicate() reads while waiting: got 1,000,000 bytes
```
In the unbounded case, the slowest 1% waited 11.8 s, longer than the worst wait during the overload itself (10 s), because the backlog outlived the spike. Bounding moved the cost either to rejected jobs or to a slowed producer.

## Related
001-rate-limiting.md, 015-message-queues.md, 020-dead-letter-queues.md, 010-circuit-breakers.md, 011-timeouts.md, 013-exponential-backoff.md, 075-ddos-protection.md, 040-deadlocks.md, 041-memory-leaks.md

## Sources
- David Yanacek, "Avoiding insurmountable queue backlogs", Amazon Builders' Library: https://builder.aws.com/content/3EuRcgkTP1MI0c7zM8W6HL3WIqA/avoiding-insurmountable-queue-backlogs
- Fred Hébert, "Queues Don't Fix Overload": https://ferd.ca/queues-don-t-fix-overload.html
- Python `subprocess` documentation, the warning on `wait()` with pipes: https://docs.python.org/3/library/subprocess.html
