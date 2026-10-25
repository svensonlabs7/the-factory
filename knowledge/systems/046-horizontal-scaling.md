# 46. Horizontal Scaling

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `--workers|gunicorn|RUN_EXECUTOR = .*max_workers=(?!1\b)|(?i:replicas:|instance_count|scale.?out)`

## What it is
Horizontal scaling (scaling out) adds more instances of a service behind a load balancer, instead of a bigger machine. It removes the single-machine ceiling and the single point of failure, but only for services whose instances do not depend on local state. The Twelve-Factor App states the requirement:
- "processes are stateless and share-nothing";
- "any data that needs to persist must be stored in a stateful backing service";
- local memory and disk serve only as "a brief, single-transaction cache";
- "sticky sessions are a violation" of the model.

Scale-out also stops paying off as coordination grows. Gunther's Universal Scalability Law models relative capacity as C(N) = N / (1 + α(N−1) + βN(N−1)):
- α is contention, waiting for shared resources, which caps throughput at 1/α;
- β is coherency, the cost of keeping shared data consistent. With β > 0, throughput "goes retrograde": it peaks at N = √((1−α)/β) and falls after that.

## When it is worth it
Scale out when one instance cannot carry the load or its failure is unacceptable, and the work divides into independent requests. First move state out of the process (sessions, counters, queues, caches that must agree) into shared backing services, and make every operation safe to run on any instance. When the bottleneck is a shared resource (one database, one lock, an external quota), more instances add contention, not capacity. Below the load one instance handles, scaling out adds a load balancer, shared state and coordination for nothing.

## How it fails
- **In-process state split across instances:** counters, rate limits, sessions or burst detectors kept in memory see only their share → limits are exceeded and alarms never fire (proof A).
- **Single-instance assumptions:** startup recovery, a scheduler or a check-then-act that relied on one event loop now runs on every instance (052-blue-green-deployment.md).
- **Sticky sessions:** requests are pinned to the instance holding their state → uneven load, and lost sessions when that instance dies.
- **Shared bottleneck:** all instances serialize on one database row, lock or file → throughput flattens and then falls (proof B, the USL's retrograde region).
- **Local disk as storage:** files written on one instance are missing on the others.
- **Caches that must agree but cannot:** per-instance caches serve different answers to the same user.

## Review checklist
- [ ] **Is all state that must be shared kept outside the process?** · Applies when: the diff adds state (counters, rate limits, sessions, queues, dedupe records) to a service that runs, or is meant to run, as more than one instance. · Block if: the state lives in process memory or on local disk, where each instance would see only its share.
- [ ] **Does any code assume it is the only instance?** · Applies when: the diff adds startup work, scheduled jobs or check-then-act logic to a horizontally scaled service. · Block if: running it on every instance at once would duplicate work or break an invariant, with no lock, leader or idempotency.
- [ ] **Does added capacity reach the bottleneck?** · Applies when: the diff adds instances or replicas to raise throughput. · Block if: the instances share a resource (a database, lock or quota) measured to be the bottleneck, so more of them only adds contention.
- [ ] **Are sticky sessions avoided?** · Applies when: the diff configures load balancing. · Block if: correctness depends on session affinity.
- [ ] **Is scale-out justified?** · Applies when: the diff introduces multiple instances or a load balancer. · Block if: one instance carries the measured peak with room to spare, and its failure is acceptable or handled by a restart. · tripwire

## In the factory
- The adapter is deliberately single-instance and cannot be scaled out as written. Its state is local:
  - the in-memory run queue (`RUN_EXECUTOR`, `factory/intake/webhook_adapter.py:151`);
  - the in-memory rejection-burst detector (`_recent_rejections`, `_burst_open`, `:550-551`, with `REJECTION_BURST = 20`, `:77`), which two copies would split so that no burst is ever detected (proof A);
  - the per-process `HEARTBEAT_LOCK`;
  - a capacity check whose atomicity relies on one event loop (`:227-232`);
  - `FETCH_HEAD` in the shared checkout (039-race-conditions.md).
- Scaling out would not help anyway. The binding resource is the Claude plan's usage, which more adapters do not add (092-throughput.md).
- The right posture is to enforce single-instance, not to scale. That is the `flock` guard in the medium Blue-Green row (052-blue-green-deployment.md, 033-leader-election.md).
- Not applicable at today's load: multiple instances, load balancing and shared state stores.

## Proof
`pytest -s knowledge/systems/proofs/046_horizontal.py` (Python 3.11):
- A is the real adapter through `tests/test_adapter.py`'s fixture, then a second import of the module on the same files, acting as a second instance behind round-robin.
- B uses real processes contending for an `fcntl.flock`-guarded counter file, with an fsync on each increment, for 2 s each.
```
A  30 bad requests, one adapter:            open_incidents = '20 rejected requests in the last hour'
A  30 bad requests, two adapters round-robin: open_incidents = 'none' (each copy counted 15 and 15)
B  1 processes sharing one locked counter:    17523 increments/s
B  2 processes sharing one locked counter:    28512 increments/s
B  4 processes sharing one locked counter:    25956 increments/s
B  8 processes sharing one locked counter:    21510 increments/s
```
In B, throughput peaks at 2 processes and then declines: the USL's retrograde region, caused by lock coordination.

## Related
047-vertical-scaling.md, 045-autoscaling.md, 052-blue-green-deployment.md, 033-leader-election.md, 001-rate-limiting.md, 092-throughput.md, 030-sharding.md

## Sources
- "VI. Processes", The Twelve-Factor App: https://12factor.net/processes
- Neil Gunther, "Universal Scalability Law", Performance Dynamics: http://www.perfdynamics.com/Manifesto/USLscalability.html
