# 57. Liveness & Readiness Probes

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
Probes are health checks with an automatic action attached. A **liveness** probe asks whether the process is stuck in a way only a restart can fix, such as a deadlock; on failure the supervisor restarts it. A **readiness** probe asks whether it can take traffic right now (warming up, waiting on a dependency, overloaded); on failure it is taken out of rotation but left running. A **startup** probe holds the other two off while a slow starter initializes. The rule that prevents most probe outages: liveness checks only the process itself, and dependencies belong in readiness, because restarting a healthy process never fixes a broken dependency. A process that simply exits needs no liveness probe; any supervisor already restarts it.

## When it is worth it
Liveness is worth it when a process can hang without exiting (a deadlock, a wedged event loop) and a restart is cheap and safe. Readiness is worth it when a balancer or queue can send work elsewhere, or hold it, while an instance is not ready. Startup probes are worth it when startup time varies or is long. They are over-engineering without an orchestrator or balancer to act on them. Restarts are also expensive wherever a restart kills work in progress, as it kills a running build in the factory: there, prefer alerting a human to automatic restarts.

## How it fails
- **Liveness checks a dependency:** a shared database or API blips → every instance fails liveness and restarts at once, which fixes nothing, drops in-flight work, and adds startup load.
- **Initial delay shorter than startup:** the probe kills the app before it finishes starting → a crash loop that never serves.
- **Readiness on a shared dependency with tight timeouts:** every instance turns unready together → zero instances in rotation.
- **Probing the wrong thing:** the probe hits a side thread or a separate status server that answers while the serving path is stuck → a zombie that looks alive.
- **Tight timeouts under load:** slow-but-working instances are restarted → their load shifts to the rest, which then fail too (a restart cascade).
- **Restart kills work:** a supervisor restarts a process mid-job → the job is lost or marked failed.

## Review checklist
- [ ] **Does liveness check only the process itself?** · Applies when: the diff adds or changes a liveness probe, watchdog or restart-on-failure rule. · Block if: it fails when an external dependency fails.
- [ ] **Does the probe exercise the path it vouches for?** · Applies when: the diff adds a liveness or health signal. · Block if: it is produced by a side thread, timer or separate server that keeps answering while the request path is stuck, and something acts on it as proof of serving.
- [ ] **Can the app finish starting before liveness acts?** · Applies when: the diff adds a probe, or makes startup slower (migrations, cache warming, model loading). · Block if: the probe's initial delay or startup allowance is shorter than the slowest observed startup.
- [ ] **Does an automatic restart account for work in progress?** · Applies when: the diff adds an automated restart of a process that runs jobs. · Block if: a restart kills in-flight work with no shutdown grace and no record that the work was interrupted.
- [ ] **Are probe timeouts and thresholds forgiving?** · Applies when: the diff sets probe timeouts or failure thresholds. · Block if: a single slow response, or a timeout below normal peak latency, triggers the action.

## In the factory
- `factory/intake/com.svenson.factory-intake.plist:38-39`, `infra/cloudflare-tunnel/com.cloudflare.cloudflared.plist:5`: launchd restarts the adapter and the tunnel when they exit. That is the "process crashes on its own" case, which needs no probe. Right.
- `factory/intake/webhook_adapter.py:732`: `_recover()` runs at import, before uvicorn serves a request, so runs left in flight are closed before new ones are accepted. Correct startup ordering. Right.
- `factory/build/run_agent.py:30-31`, `factory/build/egress.sh:33-41`: no sandbox starts until egress.sh has proven the network lock-down, and it exits non-zero otherwise. A readiness gate that fails closed. Right.
- `factory/intake/webhook_adapter.py:157-170`, `:84`: `alive_at` is stamped by a separate thread, so it proves the process exists, not that requests are served. Today every reader goes through HTTP (`/heartbeat`, `/command/data`), and those hang with a wedged loop, so a watcher still notices. Keep it that way: read `alive_at` only through the HTTP path, with a timeout, never from the file.
- No automatic restart on a hang, and none wanted: a restart kills the build in progress (`_recover` marks it `error`), and nothing is known to wedge the loop. A watcher polling `/health` with a timeout, and a human, is the right response at this load.
- Not applicable at today's load: Kubernetes probes, readiness-based rotation and startup probes. There is one process, no balancer and a fast start.

## Proof
`pytest -s scratchpad/mastery/057_probes.py`. A uses the real adapter (one event loop, lifespan running) with a handler that blocks the loop for 3 s:
```
A  /health took 2.7 s while the loop was blocked; alive_at was stamped 13 times meanwhile
```
B is a simulation of one pod over 600 s. Its shared dependency is down from 120 to 300 s, so 420 s of service are possible. Probes run every 10 s, and 3 failures trigger a restart:
```
B  case                                          restarts  seconds served of 420 possible
B  liveness checks the dependency                     4       390
B  liveness checks only the process                   0       400
B  startup 90 s, liveness delay 30 s                 11         0
B  startup 90 s, startup probe                        0       330
```
In the simulation, liveness on a dependency caused 4 pointless restarts during the outage. Each would have killed a running factory build. A liveness delay shorter than startup crash-looped and never served.

## Related
056-health-checks.md, 011-timeouts.md, 014-idempotency.md, 008-kubernetes.md, 010-circuit-breakers.md, 058-monitoring.md, 043-thread-safety.md, 054-rolling-deployments.md, 095-network-partitions.md

## Sources
- "Pod Lifecycle: Container probes", Kubernetes documentation: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
- "Configure Liveness, Readiness and Startup Probes", Kubernetes documentation: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Colin Breck, "Kubernetes Liveness and Readiness Probes: How to Avoid Shooting Yourself in the Foot": https://blog.colinbreck.com/kubernetes-liveness-and-readiness-probes-how-to-avoid-shooting-yourself-in-the-foot/
