# 89. Cold Starts

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

## What it is
A cold start is the extra time a request pays when no warm instance is ready: provisioning the environment, loading code and dependencies, and running initialization before the first request is handled. AWS Lambda's documentation describes the phases: an `Init` phase that starts extensions, bootstraps the runtime and runs the function's static code, limited to 10 seconds. Warm invocations then reuse the environment and skip all of it. It notes cold starts "typically occur in under 1% of invocations" and range "from under 100 ms to over 1 second". The largest contributor is usually initialization code: imported libraries, package size, and connections set up at start.

The mitigations trade money or complexity for latency:
- keep instances warm (Lambda provisioned concurrency, Cloud Run minimum instances, which "avoid slow container start times" but are billed while idle);
- snapshot an initialized environment (Lambda SnapStart);
- make initialization smaller: import only what is used, load lazily, reuse connections across invocations.

## When it is worth it
Cold starts matter when they are a noticeable share of a request's latency and they hit users: scale-to-zero functions, autoscaled services under spiky load (045-autoscaling.md), and anything restarted often. Measure the cold path separately from the warm one, then decide between warm capacity and a lighter start. When start-up is a few percent of a long job, or the service never scales to zero, optimizing it is over-engineering.

## How it fails
- **Users pay for initialization:** the first request after scale-up or idle waits seconds for runtime start and imports → tail latency is dominated by cold starts on spiky or low-traffic services.
- **Heavy imports:** a large SDK imported in full adds seconds to every start, even when one small part is used.
- **Cold caches after a start:** the instance is up, but its caches and connection pools are empty, so the first requests are slow and hammer dependencies (002-caching.md).
- **Initialization that does work it should not:** network calls or migrations at import time make starts slow, and make them fail when a dependency is down (055-rollbacks.md: `_recover` at import).
- **Warm-instance costs ignored:** minimum instances or provisioned concurrency are billed around the clock for a latency gain nobody needed.
- **Timeouts shorter than the cold path:** a health check or client timeout tuned on warm instances kills or abandons cold ones.

## Review checklist
- [ ] **Is the cold path measured?** · Applies when: the diff adds a service that scales to zero or autoscales, or changes its start-up work. · Block if: there is no measurement of time-to-first-response from a cold start, and that path is user-facing.
- [ ] **Does start-up avoid needless work?** · Applies when: the diff adds imports or initialization at module load or process start. · Block if: it does network calls, heavy computation, or loads large dependencies that most requests do not need, on a path where start-up latency matters.
- [ ] **Do timeouts and probes allow for a cold start?** · Applies when: the diff sets readiness or liveness probes, health-check timeouts or client timeouts for a service that cold-starts. · Block if: they are shorter than the measured cold-start time, so new instances are killed or abandoned before they finish starting.
- [ ] **Is warm capacity justified by measured cold-start impact?** · Applies when: the diff adds minimum instances, provisioned concurrency or keep-warm pings. · Block if: no measurement shows cold starts hurting a user-facing latency target.

## In the factory
Measured on this host:
- **Adapter:** time from launch to its first `/health` answer is about 0.5 s (three scratch starts: 0.59, 0.52, 0.52 s). Its import-time `_recover` does only local file work. The adapter never scales to zero, so this is paid only on deploy and restart. Right.
- **Builder, per run:**
  - the sandbox container start: `docker run` of the pinned agent-server image took 5.4, 3.8 and 3.6 s;
  - the builder's OpenHands imports: 8.8 s on a cold disk cache, then about 4 s;
  - each round therefore pays roughly 8 to 15 s of start-up, about 3% of a 315 to 406 s round. Not worth optimizing.
- **Rare, true cold starts:** a fresh builder environment means building the uv script environment, now about 307 to 328 MB on disk, from the network. That happens after a cache clean or dependency drift (108-dependency-hell.md).
- **CI:** each job pays its install steps (4 to 8 s) on a fresh GitHub runner (107-build-caching.md).
- Not applicable at today's load: warm pools, provisioned concurrency, snapshots and keep-warm pings.

## Proof
Run on this host:
- `/usr/bin/time -p docker run --rm --network none ghcr.io/openhands/agent-server:1.54.0-python true`, three times: `real 5.42`, `3.79`, `3.64`.
- `uv run --script scratchpad/mastery/089_agent_imports.py` (the builder's real header and imports): `imports 8.77 s` (real 10.04), `4.12 s` (real 4.75), `4.00 s` (real 4.60).
- A scratch uvicorn running this working copy's adapter, launch to first `/health`: `0.59 s`, `0.52 s`, `0.52 s`.
- `du -sh ~/.cache/uv/environments-v2/run-agent-*`: `307M`, `328M`. Two builder environments exist, because the dependency tree drifted between builds.

## Related
045-autoscaling.md, 090-serverless-limits.md, 108-dependency-hell.md, 107-build-caching.md, 057-liveness-readiness-probes.md, 091-latency.md

## Sources
- "Understanding the Lambda execution environment lifecycle", AWS Lambda Developer Guide: https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html
- "Set minimum instances", Google Cloud Run documentation: https://docs.cloud.google.com/run/docs/configuring/min-instances
