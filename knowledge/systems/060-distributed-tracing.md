# 60. Distributed Tracing

Track: C. Observability · Status: proven · Updated: 2026-10-18

## What it is
A trace follows one request or job through every component it touches. Each unit of work is a span, with a name, a start and end time, a parent span, and attributes. All spans of one operation share a trace ID. The ID is passed between components (context propagation) so the spans can be joined into a tree that shows where the time went and where it failed.

W3C Trace Context standardises propagation over HTTP with the `traceparent` header: a version, a 16-byte trace ID, an 8-byte parent ID and flags. OpenTelemetry is the common toolkit for creating and exporting spans. The minimum form of the idea, before any tooling, is a correlation ID written into every record a component makes about the operation, so the records can be joined later.

## When it is worth it
Full tracing (OpenTelemetry SDKs, collectors, a trace store, sampling) pays off when one request crosses many services and nobody can tell which hop is slow or failing. For a single pipeline with a few components, a correlation ID carried everywhere is enough to rebuild the timeline on demand. Instrument deeper only where an opaque stage dominates the time and its internals need explaining.

## How it fails
- **No shared ID:** logs from the API, the worker and CI cannot be joined → every investigation is guesswork by timestamp.
- **Context dropped at one hop:** one component does not forward the ID or header → the trace breaks into unconnected pieces.
- **One giant span:** the slowest stage is a single opaque span → you know where the time went, but not why.
- **Clocks disagree:** spans from different machines are compared on skewed clocks → children appear to start before their parents (see 096-clock-skew.md).
- **Tracing everything at full volume:** cost and noise explode, so sample.
- **Tracing as a substitute for logs and metrics:** traces show one path. Rates and outliers still need metrics.

## Review checklist
- [ ] **Does the operation's ID reach every record it produces?** · Applies when: the diff adds a component, job or external call that is part of an existing operation (a run, a request). · Block if: the new component's logs, events or outputs cannot be joined back to the operation's ID.
- [ ] **Is the ID propagated across process and network boundaries?** · Applies when: the diff adds a call to another process, service, queue or CI system. · Block if: the call carries no trace or correlation ID (header, argument, commit or PR metadata) when one exists upstream.
- [ ] **Is a dominant stage broken into spans when its time needs explaining?** · Applies when: the diff touches a stage that takes most of an operation's time and is being optimised. · Block if: it is optimised without any timing of its sub-steps.
- [ ] **Is new tracing infrastructure justified by the number of services?** · Applies when: the diff adds a tracing SDK, collector or backend. · Block if: the operation crosses only a few components that a correlation ID already joins.

## In the factory
- `factory/intake/webhook_adapter.py` (`_update`, `_log_action`, `_build`): the run ID is the trace ID. It names the run's `meta.json`, `actions.jsonl` and log, the default branch (`factory/<run_id>`), the commit message (`factory: <run_id>`) and the PR body. The action log records the pushed head SHA, which joins the run to its GitHub Actions runs (`head_sha`). Right: one run's whole path can be rebuilt (proof below).
- The build round is one opaque span: 406 of 492 s, 82%. The sandbox log has the agent's steps, but not as timed events. Fine at today's load. Break it into spans only if build time becomes the thing to optimise.
- Runs from before the action log existed (6 of 8 on disk) can be joined only through `meta.json` timestamps.
- Not applicable at today's load: OpenTelemetry, W3C `traceparent` propagation and a trace backend. There is one pipeline, and the run ID already joins every component.

## Proof
`python3 -I scratchpad/mastery/060_trace.py .factory-logs 920d7293`: the run's records joined to GitHub Actions by its pushed SHA (read-only API):
```
trace for run 920d7293: join keys run_id=920d7293, head sha=2c8fb9a2f606, 3 workflow runs found by sha

       0s      492s     492s  run 920d7293 (completed)
       0s      406s     406s    build round 0 (sandbox agent, exit 0)
     407s      410s       3s    gh pr create
     410s      492s      82s    adapter waits for required checks
     414s      419s       5s      CI static / secrets (success)
     414s      425s      11s      CI qa-gate / ux-laws (success)
     414s      438s      24s      CI qa-gate / ponytail-review (success)
     414s      444s      30s      CI tests / tests (success)
     415s      428s      13s      CI static / lint (success)
     415s      476s      61s      CI qa-gate / thermo-nuclear (success)

where the 492 s went: building 406 s (82%), waiting for the gate 82 s (17%)
```
The gate's critical path is thermo-nuclear (61 s). The adapter saw the result 16 s after the last job ended, which matches its 15 s `CHECKS_POLL`.

## Related
059-logging.md, 061-metrics.md, 096-clock-skew.md, 091-latency.md, 066-observability.md, 016-pub-sub.md, 017-event-driven-architecture.md

## Sources
- "Trace Context", W3C Recommendation: https://www.w3.org/TR/trace-context/
- "Traces", OpenTelemetry documentation: https://opentelemetry.io/docs/concepts/signals/traces/
