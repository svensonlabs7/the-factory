# 90. Serverless Limits

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)aws.?lambda|lambda_handler|cloud.?functions?|wrangler|\bserverless\b|vercel|netlify` · tripwire

## What it is
Serverless platforms run your code on demand and scale it for you, in exchange for hard limits you must design around. AWS says Lambda "is designed for short-lived compute tasks that do not retain or rely upon state between invocations". Its published limits include:
- a function timeout of 900 seconds (15 minutes);
- memory of 128 MB to 10,240 MB;
- 6 MB each for a synchronous request and response;
- `/tmp` storage of 512 MB to 10 GB;
- 250 MB for an unzipped deployment package, or 10 GB for a container image;
- 1,000 concurrent executions by default.

Cloudflare Workers sets different ones: 128 MB of memory per isolate, CPU time of 10 ms (free) or 30 s by default and up to 5 minutes (paid), "no hard limit on duration for HTTP-triggered Workers", and 15 minutes for cron and queue consumers.

When an invocation reaches a limit, the platform ends it, and any work held only in that invocation is lost. Long work has to be split into steps that checkpoint their progress and can be re-invoked: Step Functions, durable functions, queues.

## When it is worth it
Serverless is worth it for event-driven, short, stateless work with spiky or low traffic: webhooks, small API handlers, scheduled tasks, glue between services. You pay nothing while idle and manage no servers. Check the limits before choosing it, not after:
- longest run time against the timeout;
- payload sizes;
- memory and local disk;
- start-up time (089-cold-starts.md);
- concurrency;
- the need for a daemon or privileged runtime (Docker, long-lived connections).

Work that runs for tens of minutes, needs Docker, or keeps state between requests belongs on a long-lived host. Forcing it into serverless means building checkpointing for no benefit.

## How it fails
- **Killed at the timeout:** a job that sometimes outlasts the limit is ended mid-way, its in-memory progress lost, and a blind retry repeats the same fate (proof A).
- **Payload over the limit:** a response or event that grows past the payload cap starts failing in production on the largest inputs.
- **Hidden state between invocations:** code relies on `/tmp` or globals surviving, which works while the instance stays warm and breaks when it is recycled.
- **Concurrency limits and throttling:** a burst exceeds the account's concurrency, and invocations are throttled or queued.
- **Wrong runtime assumptions:** the workload needs a Docker daemon, a GPU, long-lived sockets or background threads that the platform does not provide.
- **Cost surprises:** a long or busy workload costs more per unit of work than a small always-on host.

## Review checklist
- [ ] **Does the longest realistic run fit the platform's timeout with margin?** · Applies when: the diff deploys work to a function platform, or adds a step to one. · Block if: the observed or allowed maximum duration is near or above the platform's limit, and the work is not split into checkpointed steps.
- [ ] **Is long work checkpointed and safe to re-invoke?** · Applies when: the diff runs multi-step work on a platform that can kill it at a limit. · Block if: progress lives only in memory, so a kill loses it, or re-invoking repeats completed side effects.
- [ ] **Do payloads, memory and disk stay inside the limits at the largest input?** · Applies when: the diff sends, returns or buffers data in a serverless function. · Block if: the largest expected payload, memory or `/tmp` use is not checked against the platform's limits.
- [ ] **Does the code rely only on state that survives invocations?** · Applies when: the diff keeps data in globals or `/tmp` of a serverless function. · Block if: correctness, not only speed, depends on that data persisting between invocations.
- [ ] **Does the workload fit serverless at all?** · Applies when: the diff moves a service to a serverless platform. · Block if: it needs a daemon (Docker), long-lived connections, runs longer than the limit, or holds state across requests.

## In the factory
- The factory runs on a long-lived host by necessity. Its workloads break serverless limits:
  - each build round may run up to `AGENT_TIMEOUT = 1800` s (`factory/intake/webhook_adapter.py:53`), twice Lambda's 900 s. Observed rounds are 315 s and 406 s;
  - the sandbox needs a Docker daemon and the 9.06 GB agent-server image (`factory/build/run_agent.py:24`), which Lambda does not provide;
  - the adapter keeps its queue and burst state in process (046-horizontal-scaling.md).

  Right.
- The pieces that would fit (the `/trigger` webhook with a body of about 100 bytes, and `/command/data` at about 6 KB) are coupled to that state. Moving them gains nothing for one operator.
- The factory's long build is already checkpointed the way serverless demands: the run record and pushed commits survive a kill (019-saga-pattern.md). A restart closes the run as `error` rather than resuming it (the Rolling Deployments and Message Queues rows in GAPS.md).
- Not applicable at today's load: functions, durable executions and serverless concurrency limits.

## Proof
`python3.11 -I knowledge/systems/proofs/090_serverless.py`. A runs a real child process killed at a 2 s limit, doing a 12-step job at 0.25 s per step (3 s in total). B checks the factory's measured workload against Lambda's published limits:
```
A  straight through     : 4 invocations, finished False, steps kept 0/12
A  checkpoint + re-invoke: 2 invocations, finished True, steps kept 12/12
B  build round 406 s (cap 1800 s) vs Lambda 900 s max: fits; the cap itself exceeds it by 900 s
B  sandbox needs a Docker daemon and a 9.06 GB agent-server image: Lambda gives no Docker daemon; image limit 10 GB
B  /command/data response ~6 KB vs 6 MB sync payload; /trigger body ~100 B: fit
```
Re-invoking the same uncheckpointed job four times made no progress. With a checkpoint after each step, the second invocation finished.

## Related
089-cold-starts.md, 045-autoscaling.md, 019-saga-pattern.md, 011-timeouts.md, 046-horizontal-scaling.md, 088-cost-optimization.md

## Sources
- "Lambda quotas", AWS Lambda Developer Guide: https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html
- "Limits", Cloudflare Workers documentation: https://developers.cloudflare.com/workers/platform/limits/
