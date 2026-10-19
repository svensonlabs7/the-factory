# 61. Metrics

Track: C. Observability · Status: proven · Updated: 2026-10-18

## What it is
Metrics are numbers measured over time: counts, rates, durations and levels. They are cheap to store, easy to graph and the basis of alerts. Google's SRE book names four golden signals for any service:
- **Latency:** how long work takes, including how long failures take.
- **Traffic:** how much work arrives.
- **Errors:** how much of it fails, explicitly or silently.
- **Saturation:** how full the most constrained resource is.

Prometheus names four metric types:
- **Counter:** only goes up, such as events or failures.
- **Gauge:** goes up and down, such as queue depth.
- **Histogram:** a distribution, used for latency percentiles.
- **Summary.**

Good practice: count failures next to total attempts, so a failure ratio is one division; export zero rather than nothing; keep label cardinality low. Most importantly, emit a structured event or counter at the point where the thing happens. Inferring it later by searching text is unreliable.

## When it is worth it
Every service needs the four signals for its main unit of work, from day one, even if they are only computed from an event log. Saturation must be measured for whichever resource actually runs out first. Time-series databases, dashboards and exporters (Prometheus, StatsD, OpenTelemetry) pay off with several services or high event rates. A single process with a few runs a day can derive its signals from a structured event log on demand.

## How it fails
- **Measuring the wrong resource:** CPU and memory are graphed while the real limit (an API quota, a plan's usage cap, a queue's slots) is invisible.
- **Inferring counts from text:** a metric computed by grepping logs counts every mention, including tests, prompts and documentation, so the number is wrong without anyone noticing.
- **Averages only:** a mean latency hides the slow tail that users feel (see 093-p99-latency.md).
- **No zero:** a series that appears only after its first event breaks dashboards and alerts that expect it.
- **Cardinality explosion:** a label per user, URL or run ID creates millions of series and takes the metrics system down.
- **Errors without a denominator:** "12 failures" means nothing without "out of how many".

## Review checklist
- [ ] **Does the new unit of work emit its golden signals?** · Applies when: the diff adds a job type, queue or pipeline stage, or an endpoint that starts work. · Block if: nothing records its count, its failures (with the total) and its duration. A read-only route on an already-instrumented service does not need its own signals.
- [ ] **Is the binding resource measured?** · Applies when: the diff adds or changes handling of a quota, rate limit, pool or cap. · Block if: hitting or waiting on that limit emits no event, counter or gauge.
- [ ] **Is the metric emitted where the event happens?** · Applies when: the diff adds a metric or KPI. · Block if: it is derived by text search over free-form logs instead of a structured event or counter.
- [ ] **Is label cardinality bounded?** · Applies when: the diff adds labels or dimensions to a metric. · Block if: a label takes unbounded values (user ID, run ID, URL, free text).

## In the factory
- `factory/intake/webhook_adapter.py` (`_log_action`): a structured event log per run (`queued`, `round_started`, `round_finished` with seconds and exit code, `pushed`, `pr_opened`, `gate_result` with each check's result, `finished`). Together with each run's `meta.json` (`queued_at`, `started_at`, `finished_at`, `status`, `attempt`), it gives traffic, errors, latency and queue saturation without a metrics stack. Right.
- `factory/intake/webhook_adapter.py:691-712` (`/command/data`): live `pending`, `runs_24h` and rejection counts against their limits. Right.
- Gap: a Claude plan usage-limit pause, which throttles the factory's most constrained resource, writes no event (`_build_round` only overwrites HEARTBEAT and sleeps), so it cannot be counted (see GAPS.md).
- Not applicable at today's load: Prometheus, exporters and a time-series database. There are a few runs a day, and the event log is enough to compute the signals.

## Proof
`python3 -I scratchpad/mastery/061_metrics.py .factory-logs`, the four signals computed from the factory's real records:
```
runs on disk: 8 (with an action log: 2)
TRAFFIC   runs queued per day: {'2026-10-12': 3, '2026-10-14': 3, '2026-10-17': 2}
ERRORS    outcomes: {'completed': 6, 'failed': 1, 'blocked': 1}; success rate 75%
          completed on the first build (attempt 0): 3/6
LATENCY   run minutes: median 11.4, max 18.7; queue wait minutes: median 0.0, max 29.8
          build-round seconds (action log): [315, 406]
SATURATION peak runs in flight: 3 of MAX_PENDING 5; busiest day: 3 of MAX_RUNS_PER_DAY 30
          plan usage-limit hits: action-log events 0; found only by grepping raw run logs: 3 run(s)
```
Checking those 3 by hand: only `1e8e28c7` really hit the limit (3 `ConversationRunError` lines). `4981e691` matched because its agent read test code containing the message, and `acec82e0`'s task was to build the pause feature. The text-derived number over-counts 3×.

## Related
059-logging.md, 058-monitoring.md, 064-slis.md, 093-p99-latency.md, 062-alerts.md, 063-slos.md, 060-distributed-tracing.md, 066-observability.md, 091-latency.md

## Sources
- "Monitoring Distributed Systems", Google SRE book: https://sre.google/sre-book/monitoring-distributed-systems/
- "Instrumentation", Prometheus documentation: https://prometheus.io/docs/practices/instrumentation/
