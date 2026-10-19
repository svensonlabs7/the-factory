# 17. Event-Driven Architecture

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

## What it is
In an event-driven architecture, components communicate by emitting events ("this happened") rather than calling each other ("do this"). Fowler separates four patterns that share the label:
- **Event notification:** a component announces a change and others react. Coupling is low, but "the overall logical flow" is no longer visible in any one piece of code.
- **Event-carried state transfer:** events carry the data, so receivers keep their own copies and need not call back. The cost is duplicated state.
- **Event sourcing:** the event log is the source of truth, and state is rebuilt by replay. This gives an audit trail and history, but replay and event-schema changes are hard.
- **CQRS:** separate write and read models.

Two cross-cutting problems:
- **Choreography versus orchestration:** reacting components, with no one owning the flow, against one coordinator that calls each step.
- **The dual write:** updating state and publishing an event are two writes, and a crash between them leaves them inconsistent. The transactional outbox fixes this by writing the event in the same transaction as the state, with a relay publishing it afterwards, at least once.

## When it is worth it
Event-driven design is worth it when independent teams or services must react to the same facts without coordinating, when reactions are slow or many, or when an audit history of changes is a requirement. It costs visibility: tracing, correlation IDs and monitoring become how you see the flow (060-distributed-tracing.md). Within one process, or a single pipeline with one owner, an orchestrator that calls the steps in order is simpler, shows its flow in one function, and fails loudly. Event sourcing is worth it only when history itself is a product requirement.

## How it fails
- **Invisible, broken flow:** in a choreography, one subscription is misspelled, removed or never deployed → the process silently stops halfway, and no component reports an error.
- **Dual write:** state is committed but its event is not (or the reverse) → downstream views disagree with the source of truth.
- **Event treated as truth when it is best-effort:** a reader builds decisions on an audit log that is allowed to drop entries.
- **Event storms and cycles:** components react to each other's events in a loop.
- **Replay breaks:** in event sourcing, old events no longer fit the code that replays them, or their effects depended on external calls that cannot be repeated.
- **Duplicated state drifts:** copies carried by events diverge when an event is missed (016-pub-sub.md).

## Review checklist
- [ ] **Is the flow owned and visible?** · Applies when: the diff makes a multi-step process continue by reacting to events instead of explicit calls. · Block if: no component owns the end-to-end flow, and a missing or misnamed subscription would stop it silently, with no timeout, monitor or orchestrator noticing.
- [ ] **Are state and its event written atomically?** · Applies when: the diff updates state and publishes or records an event that other components act on. · Block if: they are two independent writes, and a crash between them leaves consumers acting on a state that did not happen (or missing one that did), with no outbox or reconciliation.
- [ ] **Do readers rely only on what is guaranteed?** · Applies when: the diff reads a log, event stream or audit trail to make a decision. · Block if: the stream is best-effort (writes may fail silently) and the decision does not fall back to the source of truth.
- [ ] **Can event reactions loop?** · Applies when: the diff adds a handler that emits events. · Block if: its output can trigger itself directly or through another handler, with no stop condition.
- [ ] **Is event sourcing or CQRS justified?** · Applies when: the diff introduces an event store, replay, or separate read/write models. · Block if: a state record plus an append-only audit log meets the need.

## In the factory
- The pipeline is orchestrated, not choreographed. Right:
  - `factory/intake/webhook_adapter.py:495` (`_run_agent`) runs build, push, PR and gate in one function on one worker;
  - a missing step is an exception that ends the run as `error`, not a silent stall (proof A).
- The edges are event-driven, and each has an owner who notices a stall: the `/trigger` webhook comes in, and GitHub's own workflows react to the PR. The adapter waits on the gate with a deadline (`CHECKS_TIMEOUT`, `:63`), so a gate that never reports still ends the run.
- State and events are two writes. `meta.json` (`_update`, `:127-129`) is the source of truth. `actions.jsonl` (`_log_action`, `:136-141`) is a best-effort audit log that "never raises".
  - When only the event write fails, `/status` (`:624`) returns a `completed` run whose events stop at `queued` (proof B).
  - That is right as long as nothing decides from the events. Nothing in the adapter does today. 060-distributed-tracing.md uses the log only to reconstruct timelines.
  - The third checklist item keeps it that way.
- Not applicable at today's load: event sourcing, CQRS, an outbox and a broker. There is one process, one writer, and state that is a JSON record per run.

## Proof
`pytest -s scratchpad/mastery/017_eda.py` (Python 3.11). B runs the real adapter through `tests/test_adapter.py`'s fixture, with only the `.actions.jsonl` appends failing (`OSError` 28, no space left on the device):
```
A  choreography: steps done ['built', 'pushed']; errors raised: none; nothing says the flow stopped
A  orchestration: KeyError 'open_pr' at the missing step
B  /status: status 'completed'; its events: {'counts': {'queued': 1}, 'last': 'queued'}
```

## Related
015-message-queues.md, 016-pub-sub.md, 060-distributed-tracing.md, 014-idempotency.md, 082-schema-versioning.md, 059-logging.md, 018-distributed-transactions.md, 019-saga-pattern.md

## Sources
- "What do you mean by 'Event-Driven'?", Martin Fowler: https://martinfowler.com/articles/201701-event-driven.html
- "Pattern: Transactional outbox", Chris Richardson, microservices.io: https://microservices.io/patterns/data/transactional-outbox.html
