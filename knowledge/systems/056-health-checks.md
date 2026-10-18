# 56. Health Checks

Track: A. Resilience of calls · Status: proven · Updated: 2026-10-18

## What it is
A health check is a cheap request a monitor or load balancer sends to ask whether a service can do its job. AWS separates four depths:
- **Liveness:** the process answers.
- **Local:** its own disk, daemons and config work.
- **Dependency:** it can reach and use what it needs: credentials, databases, other services.
- **Anomaly detection:** it behaves like its peers.

Shallow checks are safe to act on automatically (restart, remove from rotation). Deep checks catch more, such as expired credentials or a dead daemon, but they fail on every server at once when a shared dependency is down. Acting on them automatically can turn a dependency blip into a full outage. A check should also say which version is running, so a server running stale code is noticed.

## When it is worth it
Every long-running service needs a liveness check that something actually watches. A dependency check is worth it as soon as a service can be "up" yet unable to deliver: expired tokens, a stopped Docker daemon, a full disk. Report it to a human or a watcher, and act on it automatically only for clearly local faults. Separate liveness and readiness endpoints, fail-open load balancers and anomaly detection across a fleet matter with many instances behind a balancer. One process on one host needs a shallow check, a dependency report and a version.

## How it fails
- **Liveness only:** the process answers "ok" while it cannot do its job (logged out of GitHub, Docker stopped, disk full) → every request is accepted and fails later, after spending time and money.
- **Deep check wired to automation:** a shared dependency blips, every instance fails its check at once, and the balancer pulls them all → 100% outage, including requests that never needed the dependency.
- **Health check behind the work queue:** the check is served by the same busy worker → under load it times out, healthy servers are removed, and the overload gets worse.
- **Zombie:** a server running old code answers its check → it serves with a stale schema or stale config.
- **Silent checker:** the background thread that refreshes health dies → the last result stays frozen.
- **Expensive check:** each probe queries every dependency → the probes themselves become load.

## Review checklist
- [ ] **Does a new long-running service have a liveness check that something watches?** · Applies when: the diff adds a daemon, server or worker. · Block if: there is no endpoint or heartbeat a supervisor or monitor actually polls.
- [ ] **Can the service tell "up" from "able to deliver"?** · Applies when: the diff adds a new dependency the service cannot work without (credentials, a CLI login, a daemon, a remote API). · Block if: its failure would surface only after expensive work (a build, an LLM call) and nothing checks it first.
- [ ] **Do automated actions use only shallow or local checks?** · Applies when: the diff wires a health check to a restart, failover or load-balancer removal. · Block if: a check that includes a shared dependency can remove or restart every instance at once.
- [ ] **Is the check answered off the work path?** · Applies when: the diff adds a health endpoint. · Block if: it is served by the same worker or queue that does the real work, or it runs expensive dependency calls on every probe.
- [ ] **Does the check report the running version?** · Applies when: the diff adds or changes a health endpoint of a service that is deployed by restart. · Block if: there is no way to tell which commit is running.

## In the factory
- `factory/intake/webhook_adapter.py:627-629` (`/health`): a shallow liveness check, served by the event loop, not the run worker, so it answers during a build. Right.
- `factory/intake/webhook_adapter.py:157-170` (`_stamp_alive`): a separate thread stamps HEARTBEAT `alive_at` every minute, so a watcher can tell idle from dead. If the thread dies, `alive_at` freezes and the watcher sees "dead". That fails safe. Right.
- `factory/intake/com.svenson.factory-intake.plist:38-39`: launchd `KeepAlive` restarts the adapter when it exits. That is the automated action, driven by process exit, the shallowest possible signal. Right.
- `infra/cloudflare-tunnel/config.yml`: `/health` is routed on the intake hostname behind Access, so an external probe sees the whole path (Cloudflare, tunnel, adapter). Right.
- Gap: nothing reports whether the factory can deliver (Docker and Colima, the egress proxy, `gh` auth, the Claude token, free disk). A logged-out `gh` is found only when a run fails after building (see GAPS.md).
- Gap: `/health` does not report the running commit. After a merge the adapter must be restarted by hand, and only comparing the process start time to the merge time shows whether that happened (see GAPS.md).
- Not applicable at today's load: separate liveness and readiness endpoints for a balancer, fail-open routing, fleet anomaly detection. There is one instance and no balancer.

## Proof
`pytest -s scratchpad/mastery/056_health_checks.py`. A uses the real adapter through `tests/test_adapter.py`'s fixture, with `gh` replaced by one that is logged out:
```
A  /health before: {'status': 'ok'}  after: {'status': 'ok'}
A  run: status='error' events=['queued', 'round_started', 'round_finished', 'pushed', 'finished']
A  error: ...'dy Factory build 1bcdafbb\n\nTask: t0: To get started with GitHub CLI, please run:  gh auth login'
```
`/health` said ok throughout, while the run built and pushed, then died at PR creation. B is arithmetic, not a measurement: it illustrates AWS's fleet warning with 10 servers, where 70% of requests need no shared dependency and that dependency is down:
```
B  shallow liveness     servers in rotation 10/10   served 70%
B  deep, no fail-open   servers in rotation  0/10   served 0%
B  deep, fail-open      servers in rotation 10/10   served 70%
```

## Related
057-liveness-readiness-probes.md, 010-circuit-breakers.md, 058-monitoring.md, 062-alerts.md, 020-dead-letter-queues.md, 011-timeouts.md

## Sources
- David Yanacek, "Implementing health checks", Amazon Builders' Library: https://builder.aws.com/content/3Ev53O39izHCtWLzp4XU6t8PC1O/implementing-health-checks
- "Health Endpoint Monitoring pattern", Azure Architecture Center: https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring
