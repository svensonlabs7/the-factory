# 54. Rolling Deployments

Track: E. Delivery and change · Status: proven · Updated: 2026-10-18

## What it is
A rolling deployment replaces the instances of a service a few at a time instead of all at once, so the service keeps serving throughout. Each step:
1. Take an instance out of the load balancer and let its in-flight work drain.
2. Replace it.
3. Wait until the new instance passes its readiness check.
4. Put it back, then move on.

Kubernetes expresses this with `maxUnavailable` (how many instances may be down) and `maxSurge` (how many extra may run), both 25% by default. A new pod counts as available only once it is Ready. Amazon replaces at most a third of a region's hosts per batch, keeps at least two thirds of capacity serving, and rolls back automatically when alarms fire during the bake time.

The alternative, Recreate, stops everything and then starts the new version: simple, with downtime. A rolling deploy also means old and new versions run side by side, so the two must be compatible (see 055-rollbacks.md).

## When it is worth it
A rolling deploy needs at least two instances behind something that routes around the one being replaced, plus a readiness signal. It is worth it once a service has redundant instances and must not drop requests during a deploy. With one instance there is nothing to roll: a deploy is a Recreate. The questions then become how long the gap is, who retries across it, and what work in flight is lost. Adding a second instance just to deploy without a gap is over-engineering when callers can retry and the gap is a second.

## How it fails
- **No readiness gate:** the new instance is put back when its process starts, before it listens → requests to it fail during every step.
- **No drain:** an instance is killed with requests or jobs in flight → those are cut off mid-way.
- **Too much at once:** `maxUnavailable` too high, or batches too big → the remaining capacity is overloaded during the deploy.
- **Mixed versions incompatible:** old and new instances disagree on a format or protocol while both serve → errors that last exactly as long as the rollout.
- **Stalled rollout nobody sees:** new instances never become ready. Kubernetes only reports `ProgressDeadlineExceeded` and does not roll back on its own.
- **Single instance with long jobs:** the "deploy" is a restart that kills every running job.

## Review checklist
- [ ] **Does a new instance take traffic only after it is ready?** · Applies when: the diff changes deploy config, health or readiness endpoints, or the service's startup. · Block if: traffic can reach the instance before its readiness check passes, or the check does not cover what requests need.
- [ ] **Is in-flight work drained or resumable?** · Applies when: the diff adds long-running requests, background jobs or workers to a service that is deployed by restarting it. · Block if: a deploy kills that work and it is neither drained first nor resumed after.
- [ ] **Can old and new versions run side by side?** · Applies when: the diff changes a format, protocol or schema for a service deployed with more than one instance. · Block if: an instance on the old version would fail on what the new version writes or sends.
- [ ] **Is enough capacity kept during the deploy?** · Applies when: the diff sets rollout batch sizes (`maxUnavailable`, `maxSurge`, batch percent). · Block if: the instances left serving cannot carry peak load.
- [ ] **Is a second instance justified?** · Applies when: the diff adds replicas or a load balancer only to deploy without downtime. · Block if: callers already retry across a restart gap of seconds and nothing requires zero dropped requests.

## In the factory
- The adapter is one process (`factory/intake/com.svenson.factory-intake.plist`, a launchd `KeepAlive` job), so a deploy is a Recreate: `launchctl kickstart -k` (`factory/intake/README.md:89`). The request gap is under a second (proof below). Callers of `/trigger` see a 502 from the tunnel for that moment.
- Gap (medium): nothing checks for in-flight runs before a deploy. The restart kills the single run worker mid-run, and `_recover` (`factory/intake/webhook_adapter.py:715-732`) closes every in-flight run as `error`. The run's work and plan usage are lost, and its sandbox may be orphaned (see the Idempotency row in GAPS.md). On 2026-10-10, one restart ended 4 runs at once (`.factory-logs/archive/factory-20261010-*.meta.json`, all `"the service restarted during the run"`, same `finished_at`). The deploy procedure has no "wait until idle" step (see GAPS.md).
- `_recover` itself is right: it turns runs killed by the restart into a visible `error` instead of leaving them "running" forever.
- Not applicable at today's load: a second adapter instance, a load balancer, rollout batches and automated rollback. There is one host, one queue and one operator, and a gap under a second is acceptable once runs are not killed.

## Proof
`python3 -I knowledge/systems/proofs/054_rolling.py <repo>` runs this working copy's real adapter under uvicorn on scratch ports with a scratch `FACTORY_ROOT`, so the live adapter and its logs are untouched. A client sends `GET /health` every 10 ms throughout:
```
A  recreate, 1 instance:             44 of 118 requests failed; deploy took 0.7 s
B  rolling, 2 instances, no gate:    22 of 171 requests failed; deploy took 1.4 s
C  rolling, 2 instances, readiness:  0 of 169 requests failed; deploy took 1.4 s
```
Rolling alone is not enough: without the readiness gate (B), the new instance is back in rotation before uvicorn listens. The live in-flight loss is from the archived run records above, not re-run.

## Related
055-rollbacks.md, 052-blue-green-deployment.md, 053-canary-releases.md, 056-health-checks.md, 057-liveness-readiness-probes.md, 006-ci-cd.md, 015-message-queues.md

## Sources
- "Deployments" (RollingUpdate, Recreate, progressDeadlineSeconds), Kubernetes documentation: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- "Automating safe, hands-off deployments", Amazon Builders' Library: https://builder.aws.com/content/3ErTKQOTKc5NIw031UePBPxTQ6I/automating-safe-hands-off-deployments
