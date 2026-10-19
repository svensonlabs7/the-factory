# 52. Blue-Green Deployment

Track: E. Delivery and change · Status: proven · Updated: 2026-10-18

## What it is
Blue-green deployment runs two production environments. Blue is live; green is idle. The new version is deployed to green and tested there while blue serves. A router or DNS switch then sends all traffic to green. Rolling back is switching the router back to blue, which is still running the old version. After the release settles, the idle side becomes the staging area for the next one.

The hard part is state. Both colours usually share a database, queue or disk, so:
- the shared state must work with both versions at once;
- schema changes ship separately, before the app change;
- anything that assumes it is the only instance (startup recovery, singleton workers, schedulers) must not run on both colours at once.

## When it is worth it
It is worth it when a release must switch instantly and roll back instantly, and the release can be tested on production infrastructure before it takes traffic. It costs a second full environment, a traffic switch, and versions that are compatible on shared state. Below that, a Recreate deploy (restart in place) plus a fast rollback is enough. For a single process with exclusive local state, blue-green is not just over-engineering but unsafe, unless the state is split per colour.

## How it fails
- **Shared state, singleton assumptions:** green starts, and its startup code treats blue's live work as abandoned (recovers it, deletes it, re-runs it). Both colours then run the background workers.
- **Schema not compatible both ways:** green migrates the shared database, and blue (still live, or the rollback target) breaks on the new schema.
- **Switch is not instant:** DNS TTLs and cached clients keep sending traffic to blue after the switch → a long tail of old-version requests, and rollback is just as slow.
- **In-flight work cut at the switch:** blue is stopped as soon as traffic moves → its long requests and jobs are lost. Blue must drain first.
- **Green never really tested:** smoke tests against green are skipped, so the switch is the test.
- **Idle side drifts:** the old environment's config or dependencies change between releases, so "switch back" lands on something nobody tested.

## Review checklist
- [ ] **Does anything assume it is the only running instance?** · Applies when: the diff adds startup recovery, cleanup, a scheduler or a singleton worker, in a service that is (or may be) deployed blue-green or with two copies. · Block if: a second instance on the same state would take over, delete or re-run the first one's work, and there is no lock or per-instance ownership.
- [ ] **Is the shared state compatible with both colours?** · Applies when: the diff changes a schema, file format or queue message that blue and green both read. · Block if: the old colour, which is the rollback target, cannot read what the new one writes (see 055-rollbacks.md).
- [ ] **Does the old colour drain before it stops?** · Applies when: the diff changes the switch or teardown step. · Block if: blue is stopped while it still has in-flight requests or jobs.
- [ ] **Is green verified before the switch?** · Applies when: the diff adds or changes a blue-green pipeline. · Block if: traffic moves to green with no health or smoke check against green itself.
- [ ] **Is a second environment justified?** · Applies when: the diff introduces blue-green for a service. · Block if: a restart in place plus rollback meets the need, or the service's state is exclusive to one process.

## In the factory
- The factory does not deploy blue-green: one launchd process, restarted in place (see 054-rolling-deployments.md). That is the right choice. Its run records, HEARTBEAT and `FACTORY_ROOT` checkout are exclusive to one process by design: one run worker (`factory/intake/webhook_adapter.py:151`, `RUN_EXECUTOR` with `max_workers=1`), and `_recover` at import (`:715-732`) assumes every in-flight run belongs to a dead predecessor.
- Gap (medium, raised in review 50): nothing enforces a single instance. A second copy started on the same `FACTORY_ROOT` (and the default, `:50`, is the operator's working copy, the same as the live adapter's) does three things, all shown in the proof:
  - it marks the live adapter's in-flight run `error` at import;
  - it accepts and builds runs in parallel with the live worker, counting only its own runs against the in-flight cap;
  - its pushes share `FETCH_HEAD` with the live worker (039-race-conditions.md).

  A manual `uvicorn` started for debugging without `FACTORY_ROOT` is enough to trigger it. So is a second start on the live port 7654, which fails to bind but only after its import has already marked the live run `error` (review 50; see GAPS.md). The bound port is not the single-instance lock that 037 once called it.
- Not applicable at today's load: a second environment, a traffic switch and shared-state migration. With one host and one operator, Recreate plus a fast rollback is enough.

## Proof
`pytest -s scratchpad/mastery/052_blue_green.py` (Python 3.11): blue and green are two imports of the real adapter module through `tests/test_adapter.py`'s fixture (fake agent sleeping 2 s, fake `gh`):
```
A  green starts while blue builds a570b746: green reports 'error' (the service restarted during the run)
A  green accepts a new run while blue's worker is still building: blue worker alive True, green's run 'running', green counts in flight 1
A  after blue's worker ends: record 'completed', blue's own events for it: ['queued', 'round_started', 'finished', 'round_finished', 'pushed', 'pr_opened', 'gate_result', 'finished']
B  green on its own root: blue's run seen as 'running' after green started, finished 'completed'; green healthy: {'status': 'ok'}
```
With shared state, the run's record flips from `running` to `error` to `completed`, its action log gets two `finished` events, and two workers build at once. With separate state (B), and blue drained before it stops, nothing collides.

Review 50 (`python3 -I scratchpad/mastery/review50_port_lock.py <repo>`, real uvicorn processes on a scratch port and root):
```
second instance on the same port: exit 3, "ERROR:    [Errno 48] error while attempting to bind on address ('127.0.0.1', 18750): address already in use"
first instance's in-flight run after the failed start: status 'error', error 'the service restarted during the run'
```

## Related
054-rolling-deployments.md, 055-rollbacks.md, 053-canary-releases.md, 039-race-conditions.md, 038-distributed-locks.md, 006-ci-cd.md, 030-sharding.md, 033-leader-election.md

## Sources
- "BlueGreenDeployment", Martin Fowler: https://martinfowler.com/bliki/BlueGreenDeployment.html
- "Blue/Green Deployments on AWS" (whitepaper), Introduction: https://docs.aws.amazon.com/whitepapers/latest/blue-green-deployments/introduction.html
