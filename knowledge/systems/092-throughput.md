# 92. Throughput

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `max_workers|--workers|ThreadPool|MAX_PENDING|MAX_RUNS_PER_DAY|(?i:\bbatch|concurren)`

## What it is
Throughput is how much work a system completes per unit of time: requests a second, jobs an hour, bytes a second. It is bounded by the slowest resource on the path, the bottleneck. Adding capacity anywhere else changes nothing.

Little's Law ties it to latency and concurrency: L = λW. The average number of items in a system equals the arrival rate times the average time each spends inside. Little's own retrospective stresses how general it is: it needs no "detailed assumptions about interarrival times, service times", and holds "independent of queue discipline". So any two of concurrency, throughput and latency determine the third.

Throughput is not the same as useful work. The Amazon Builders' Library distinguishes goodput, "the subset of the throughput that is handled without errors" and fast enough for the client to use. Under overload, a server can stay busy at full throughput while goodput collapses: it works on requests whose clients have already timed out, and "all the progress that the server made so far on that request goes to waste". Load shedding, rejecting excess work at arrival, keeps goodput near capacity.

## When it is worth it
Measure throughput and utilization of the bottleneck for any system with queues or capacity limits, and know its saturation point before production finds it. Load shedding and admission control are worth it wherever offered load can exceed capacity and callers have timeouts. Throughput engineering (more workers, batching, parallelism) is worth it only on the measured bottleneck, and only when demand approaches its capacity. For a pipeline running far below capacity, more throughput is over-engineering.

## How it fails
- **Goodput collapse:** offered load passes capacity, the queue grows, latency passes the clients' timeout, and the server spends all its time on abandoned requests. Throughput stays at 100% while useful work falls to a few percent (proof A).
- **Retries amplify overload:** timed-out clients resend, so offered load grows exactly when capacity is gone (012-retries.md).
- **Scaling the wrong resource:** more web workers in front of a saturated database, or more threads on a single lock → no gain, sometimes a loss.
- **Contention past saturation:** more concurrency than the resource can use adds queueing and context switching, and throughput falls (proof B).
- **Unbounded queues:** they hide the overload until memory or latency runs out (044-backpressure.md).
- **Unknown capacity:** nobody has measured the saturation point, so the first sign is an outage.

## Review checklist
- [ ] **Is excess load rejected before it is worked on?** · Applies when: the diff adds a service or queue whose offered load can exceed its capacity, and whose callers time out. · Block if: work is accepted without bound and processed after callers may have given up, with no admission limit, queue bound or deadline check.
- [ ] **Is the change aimed at the bottleneck?** · Applies when: the diff adds workers, parallelism or batching to increase throughput. · Block if: no measurement shows that the resource being scaled is the bottleneck at the expected load.
- [ ] **Is work discarded once its deadline has passed?** · Applies when: the diff processes queued requests that carry a client deadline or timeout. · Block if: a worker starts or continues a request whose caller has already timed out.
- [ ] **Is saturation known?** · Applies when: the diff changes capacity-relevant configuration (worker counts, pool sizes, concurrency limits). · Block if: there is no load test or measurement showing throughput and latency at and beyond the expected peak.
- [ ] **Is more throughput needed?** · Applies when: the diff adds capacity or parallelism. · Block if: measured utilization at the expected peak is low.

## In the factory
- The pipeline's bottleneck is the single run worker (`RUN_EXECUTOR`, `factory/intake/webhook_adapter.py:151`), and behind it the binding resource is the Claude plan's usage, not compute (061-metrics.md).
- From the 8 timed run records:
  - λ = 1.4 runs a day and W = 16.5 minutes in the system, so L = 0.016 runs in flight on average (Little's Law);
  - one worker at that W could do about 87 runs a day, and the configured cap of 30 a day (`MAX_RUNS_PER_DAY`, `:73`) uses it 34%.
- Admission control already sheds excess load at intake. `/trigger` answers 429 at `MAX_PENDING = 5` in flight or 30 a day (`:72-73`), so the queue cannot grow into a goodput collapse. Right (001-rate-limiting.md, 044-backpressure.md).
- The adapter's HTTP throughput is irrelevant at this load. A scratch copy serves `/health` at about 1,500 requests a second against a demand of a few a minute.
- Not applicable at today's load: more workers, batching and load testing.

## Proof
`python knowledge/systems/proofs/092_throughput.py <repo>` (Python 3.11):
- A is a discrete-event simulation of one server at 10 ms a request (capacity 100/s), with clients that give up after 1 s. Shedding rejects any request at arrival whose queue wait would exceed 100 ms.
- B load-tests a scratch uvicorn running this working copy's adapter. The client and server share the host's CPU, so B is a lower bound.
- C reads the live run records.
```
A  offered 100/s: FIFO throughput 100.0/s goodput 100.0/s | shedding throughput 100.0/s goodput 100.0/s
A  offered 150/s: FIFO throughput 100.0/s goodput   5.0/s | shedding throughput 100.0/s goodput 100.0/s
A  offered 200/s: FIFO throughput 100.0/s goodput   3.3/s | shedding throughput 100.0/s goodput 100.0/s
B  /health,  1 concurrent clients:    1540 req/s
B  /health,  8 concurrent clients:    1252 req/s
B  /health, 32 concurrent clients:     434 req/s
C  8 timed runs over 5.7 days: lambda 1.4 runs/day, mean time in system W 16.5 min, L = lambda*W = 0.016 runs in flight on average
C  one worker at W per run caps throughput at 87 runs/day; the configured cap is 30/day, so the worker is busy 34% at the cap
```
In A, past capacity, FIFO keeps the server 100% busy while only 3–5% of the work reaches a client in time. Shedding serves the full 100/s in time.

## Related
091-latency.md, 044-backpressure.md, 001-rate-limiting.md, 012-retries.md, 093-p99-latency.md, 046-horizontal-scaling.md, 028-connection-pooling.md

## Sources
- John D. C. Little, "Little's Law as Viewed on Its 50th Anniversary", Operations Research 59(3), 2011 (reprint): https://projectproduction.org/journal/reprint-littles-law-as-viewed-on-its-50th-anniversary/
- "Using load shedding to avoid overload", Amazon Builders' Library: https://builder.aws.com/content/3Eun1EEyX6p2e3VYNyRLSJzLuMV/using-load-shedding-to-avoid-overload
