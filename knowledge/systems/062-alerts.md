# 62. Alerts

Track: C. Observability · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\balert|open_incidents|rejection_burst|\bnotif(y|ication)|\bpager`

## What it is
An alert is monitoring that interrupts a person. Every alert should be urgent, important, actionable and real. Page on symptoms users feel (requests failing, work not completing, the service unreachable), not on causes such as high CPU, which belong on dashboards or tickets. The SRE workbook scores an alert rule four ways:
- **Precision:** how many pages are real.
- **Recall:** how many incidents page.
- **Detection time.**
- **Reset time.**

Two kinds of rule are needed. Event or rate rules ("too many failures") catch a service that is working badly. Absence or staleness rules ("no heartbeat for 5 minutes", "no successful run in N hours") catch a service that has stopped, which produces no failure events at all. At low traffic, rate rules break down: one failure among a few events looks like a huge error rate, and a real incident takes as long to confirm as the gap between events. The fixes are synthetic traffic, longer windows, or alerting on each meaningful event.

## When it is worth it
As soon as anyone depends on the service, it needs at least a liveness (staleness) alert and a symptom alert, delivered somewhere a person will see them (push, chat, email). Multiwindow, multi-burn-rate SLO alerts are worth it at steady, meaningful traffic. At a few events a day they cannot tell an incident from noise, so simple rules work better there.

## How it fails
- **Alert on every failure:** routine failures page constantly → people learn to ignore pages, and miss the real one.
- **Rate rules at low traffic:** too few events → false pages from one bad run, or a day before a real incident is confirmed.
- **Only event-based rules:** the service dies, emits no events, and nothing fires.
- **Cause-based pages:** CPU or disk thresholds page when users are fine, and stay silent when users are not.
- **Alert with nowhere to go:** the condition is detected and written to a file or a dashboard no one has open.
- **Slow reset:** the alert keeps firing after recovery, so people stop trusting it.

## Review checklist
- [ ] **Is there a staleness alert for the service being down?** · Applies when: the diff adds a service or worker that others depend on. · Block if: only failure events can alert, so a dead or hung process produces no alert.
- [ ] **Does the alert reach a person?** · Applies when: the diff adds an alert condition. · Block if: it only writes a file, sets a status field, or changes a dashboard, with no notification channel.
- [ ] **Does the rule fit the traffic?** · Applies when: the diff adds a rate or ratio alert. · Block if: expected events per window are too few for the threshold to separate an incident from normal failures (for example, a percentage over one hour at a few events a day).
- [ ] **Is it a symptom, and actionable?** · Applies when: the diff adds a paging alert. · Block if: it pages on a cause with no user impact, or has no action a responder could take.

## In the factory
- `factory/intake/webhook_adapter.py:77,576-579`: a burst of 20 rejected requests in an hour sets `open_incidents` in HEARTBEAT. It is a good symptom rule, but it only writes a file.
- `factory/intake/command.html:195-197`: the dashboard shows `DOWN` and changes the tab title when `alive_at` is stale. It is a good staleness rule, but only while someone has the dashboard open.
- No signal reaches a person. That is recorded as the Monitoring and Dead Letter Queues rows in GAPS.md, so no new row is added here. When it is wired, the experiment favours: page on `alive_at` stale for 5 minutes (a dead process), and on the authenticated `/health` probe failing (a wedged one, which `alive_at` misses, per 057-liveness-readiness-probes.md), page on 3 failed runs in a row, and use a dependency check before each build (056-health-checks.md) to catch a broken dependency in minutes rather than a day.
- Not applicable at today's load: burn-rate and SLO-window alerting. About 3 runs a day is too sparse for rates.

## Proof
`python3 -I knowledge/systems/proofs/062_alerts.py` simulates 30 days at about 3 runs a day, with 25% normal failures. Incident 1 (day 18): every run fails. Incident 2 (day 25): the adapter dies.
```
simulated runs: 70; normal failures before day 18: 18
page on every failed run          false pages 18 | incident 1 detected after 23 h, 19 pages | incident 2: never (no events to alert on)
page on 3 failures in a row       false pages  0 | incident 1 detected after 27 h,  1 pages | incident 2: never (no events to alert on)
page on >50% failed in 24h        false pages  5 | incident 1 detected after 29 h,  3 pages | incident 2: never (no events to alert on)
3 in a row + alive_at stale 5 min false pages  0 | incident 1 detected after 27 h,  1 pages | incident 2: 5 min
```
"3 in a row" across 20 seeds: detection median 23 h, max 38 h, with false pages in 18 days median 0 and max 2. At this traffic, every outcome-based rule needs about a day to confirm a broken dependency. Only staleness catches a dead factory.

## Related
058-monitoring.md, 063-slos.md, 065-error-budgets.md, 056-health-checks.md, 110-on-call.md, 020-dead-letter-queues.md

## Sources
- "Alerting on SLOs", Google SRE workbook: https://sre.google/workbook/alerting-on-slos/
- "Monitoring Distributed Systems" (symptoms versus causes, simple rules), Google SRE book: https://sre.google/sre-book/monitoring-distributed-systems/
