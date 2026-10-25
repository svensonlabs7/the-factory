# 66. Observability

Track: C. Observability · Status: proven · Updated: 2026-10-18

Triggers: lines `_log_action|logging\.|\blog\.(info|warning|error|exception)|_set_heartbeat|(?i:\busage\b|\bcost\b)`

## What it is
Observability is how well you can understand a system's internal state from its outputs, especially for questions nobody anticipated, without shipping new code to answer them. Monitoring covers the known unknowns: checks and thresholds you defined in advance. Observability covers the unknown unknowns: the novel failure you are debugging right now.

Telemetry (logs, metrics, traces) is the raw material, but having the three data types is not the same as being observable. OpenTelemetry calls a system "properly instrumented" when engineers can troubleshoot it without adding more instrumentation. Charity Majors stresses wide structured events: one record per unit of work with many fields, including high-cardinality ones like run ID, task or commit. Those let you slice by any dimension after the fact.

## When it is worth it
Every system needs enough of it to answer its operators' real questions: why did this run fail, where did the time go, what did it cost, what changed. The practical test is to write down the questions you will be asked in an incident and check whether today's telemetry answers them. Event stores, high-cardinality query engines and vendor platforms (Honeycomb, Datadog and the like) pay off with many services and many people debugging. A single pipeline needs complete per-run events and its binding resource recorded.

## How it fails
- **Data types without answers:** logs, metrics and a dashboard exist, but the question in front of you needs a field that was never recorded.
- **Narrow events:** each record carries a message but not the context (run, task, commit, attempt), so nothing can be sliced or joined.
- **The binding resource is invisible:** cost, quota or capacity consumption is not emitted, so there is no warning before the limit hits.
- **Lifecycle not recorded:** resources created per unit of work (containers, temp files, branches) have no start and stop events, so leaks are found only by inspecting the live system.
- **Placeholders that look like data:** a field that is always 0 or "—" passes for a measurement.

## Review checklist
- [ ] **Can the operators' likely questions be answered from existing telemetry?** · Applies when: the diff adds a new job type, stage or external dependency. · Block if: a basic question about it (did it succeed, how long, why not, what did it cost) cannot be answered without new code.
- [ ] **Is the binding resource's consumption emitted per unit of work?** · Applies when: the diff starts work that consumes a quota, budget or paid API. · Block if: the amount consumed by each unit is not recorded, or is recorded as a constant placeholder.
- [ ] **Do per-unit resources record their lifecycle?** · Applies when: the diff creates containers, processes, files or branches per unit of work. · Block if: their creation and cleanup are not recorded against the unit's ID.
- [ ] **Do events carry the unit's context?** · Applies when: the diff adds structured events. · Block if: an event lacks the identifiers (run, attempt, commit) needed to join it to the rest.

## In the factory
- `factory/intake/webhook_adapter.py` (`_log_action`, `meta.json`, `rejected.jsonl`): wide-enough per-run events with the run ID, attempt, head SHA, durations and gate results, plus a timestamped rejection log. Questions about queue wait, failed tasks, rejections and where the time went are answerable today (proof below; and 060-distributed-tracing.md). Right.
- Gap: plan usage per run is unobservable. Every `Tokens:` line in every run log reports `input (total 0)` and `output (total 0)` (32 lines, 8 runs), so the agent integration passes no usage back (see GAPS.md). Usage-limit pauses are also unrecorded (the 061-metrics.md row).
- Partial: gate results per check exist only for runs since the action log shipped (2 of 8), and an accepted trigger's source address is in the access log, which has no timestamps (the 059-logging.md row).
- Container lifecycle per run is not recorded. Low priority now that #56 stops containers on timeout, but a leak would be found only with `docker ps`.
- Not applicable at today's load: an observability platform or event store. The question battery runs in seconds over local files.

## Proof
`python3 -I knowledge/systems/proofs/066_observability.py .factory-logs`, 8 new questions put to the existing telemetry:
```
[yes    ] How long do runs wait in the queue?  median 0.0 min, max 29.8 min (meta.json)
[partial] Which gate check blocks most often?  action log covers 2/8 runs; older runs need the GitHub API
[yes    ] Which task wording ends in blocked or failed runs?  failed: 'Prune old run records...'; blocked: 'Factory pull requests are titled...'
[yes    ] When were requests rejected, and why?  13 entries with time and reason: {'Invalid signature': 13}
[partial] At what time did each accepted /trigger arrive, from which address?  time yes; address only in the untimestamped access log
[no     ] How often does the plan usage limit pause the factory?  no event is written for a pause
[no     ] How much plan usage does one run consume?  every 'Tokens:' line in every run log reports 0
[no     ] Did a timed-out run leave a container behind?  container start/stop is not recorded per run
answerable from existing telemetry: yes 3, partial 2, no 3 (of 8)
```

## Related
058-monitoring.md, 059-logging.md, 060-distributed-tracing.md, 061-metrics.md, 088-cost-optimization.md

## Sources
- "Observability primer", OpenTelemetry documentation: https://opentelemetry.io/docs/concepts/observability-primer/
- Charity Majors, "Observability is a many-splendored definition": https://charity.wtf/2020/03/03/observability-is-a-many-splendored-thing/
