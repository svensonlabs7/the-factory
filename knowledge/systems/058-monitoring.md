# 58. Monitoring

Track: C. Observability · Status: proven · Updated: 2026-10-18

## What it is
Monitoring is something other than the system watching the system, continuously, so that problems are noticed without a person happening to look. There are two kinds:
- **Black-box:** probes the service from outside, the way a user would, and tells you what is broken now.
- **White-box:** reads internal signals (metrics, heartbeats, queue depth, logs) and tells you why, and often what is about to break.

Each covers the other's blind spots. A process can report "alive" internally while users cannot reach it, and an outside probe can succeed against a cache or an edge while the service behind it is dead. Monitoring is also a system to monitor: Google's SRE workbook says alerting rules often go untested for months, so test that they fire, and treat monitoring config as code.

## When it is worth it
Every service that someone depends on needs at least one black-box probe of its real user path, with credentials if the path requires them, and one white-box liveness signal, both read by something that can alert. A dashboard nobody has open is not monitoring. Multi-region probes, synthetic transactions and full white-box metric stacks are for larger services. One factory needs one probe and one watcher.

## How it fails
- **Nobody watching:** a dashboard exists, but only shows a problem when someone opens it → outages last until a user complains.
- **Probe answered by the wrong layer:** a CDN, auth gateway or cache answers the probe without touching the origin → the probe stays green while the origin is dead.
- **White-box only:** the process stamps "alive" while the tunnel, DNS or certificate in front of it is broken → users fail and nothing notices.
- **Black-box only:** the probe sees an outage but nothing explains it.
- **Monitoring that never fires:** a rule or probe was misconfigured from day one, and nobody tested it.
- **The watcher has no path:** the signal exists but is not reachable from where the watcher runs.

## Review checklist
- [ ] **Does a new service have both a black-box probe and a white-box signal, read by something that alerts?** · Applies when: the diff adds a long-running service or public endpoint. · Block if: its health is visible only on a dashboard or in local files that nothing polls.
- [ ] **Does the probe reach the origin?** · Applies when: the diff adds or changes an external probe behind an edge, auth gateway or cache. · Block if: the probe can be answered by the edge or auth layer without touching the origin (it must authenticate, or check a response only the origin produces).
- [ ] **Can the watcher reach the signal?** · Applies when: the diff adds a health or heartbeat endpoint meant for an external watcher. · Block if: the tunnel, proxy or firewall does not route it to where the watcher runs.
- [ ] **Has the monitoring been seen to fire?** · Applies when: the diff adds an alerting rule or probe. · Block if: there is no test or recorded drill showing it fires on the failure it targets.

## In the factory
- `factory/intake/webhook_adapter.py:157-170` (`_stamp_alive`), `/heartbeat`, `/command/data`: white-box signals exist (`alive_at` every minute, run state, limits), and the dashboard shows them. Right, as signals.
- `pmset -g custom`: on AC power the Mac is set to `sleep 0` (never), so the factory does not stop when the machine is idle. Right.
- Gap (medium): nothing watches. Every client in the access log is local or the operator's own home addresses (the dashboard). `/heartbeat` is not routed by the tunnel (`infra/cloudflare-tunnel/config.yml:6`), so the intended watcher, Grok Bot, cannot reach it. A probe without credentials gets the same Cloudflare Access 401 for `/health` and for a path that does not exist, so it learns nothing about the origin (see GAPS.md).
- Not applicable at today's load: multi-location probes and synthetic transactions. One authenticated probe of `/health`, plus one reader of `/heartbeat` with alerting, covers it.

## Proof
Black-box probe from this machine, without credentials:
```
https://factory.svensonlabs.dev/health                  -> 401 (37816 bytes)
https://factory.svensonlabs.dev/this-path-is-not-routed -> 401 (37816 bytes)
```
The answers are byte-identical, so Cloudflare Access replies before the tunnel or origin is consulted. Who has polled the adapter (`intake.out.log` client addresses, behind cloudflared's forwarded headers): `127.0.0.1` (160), and addresses in this home's own IPv6 prefix and IPv4 (about 5,700, the operator's dashboard). No external watcher appears. `pmset -g custom`: `AC Power: sleep 0`.

## Related
056-health-checks.md, 057-liveness-readiness-probes.md, 062-alerts.md, 061-metrics.md, 020-dead-letter-queues.md

## Sources
- "Monitoring Distributed Systems" (black-box and white-box monitoring), Google SRE book: https://sre.google/sre-book/monitoring-distributed-systems/
- "Monitoring", Google SRE workbook: https://sre.google/workbook/monitoring/
