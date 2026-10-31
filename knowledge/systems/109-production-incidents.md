# 109. Production Incidents

Track: L. Operations · Status: proven · Updated: 2026-10-19

Triggers: lines `_set_heartbeat\(|open_incidents|pipeline_status|blocking_reason|_finish\(`

## What it is
A production incident is an unplanned disruption — an outage, data problem, or degraded service — that needs a coordinated response to restore normal operation. Incident *management* is the process that handles it: **detect** (an alert or report), **declare** and set a **severity** (how bad, how urgent), **coordinate** under a clear owner (an incident commander who runs the response, with others handling operations and communications), **mitigate** to stop user impact, then **resolve** and hand off to a postmortem (111-postmortems.md). The central arithmetic is that customer impact lasts from when the problem starts until it *stops hurting users* — which is the moment you mitigate, not the moment you find root cause. Two rules follow (proof): detection dominates (an undetected incident runs until someone stumbles on it), and you mitigate before you diagnose (roll back, fail over, or disable the feature to end impact, then root-cause off the clock). Severity decides how much response to spin up; most events are low-severity and handled routinely, a few warrant waking people.

## When it is worth it
- A lightweight declared process is worth it the moment an outage would have real cost and more than one person could respond — it prevents the chaos of an uncoordinated scramble (duplicated actions, no owner, conflicting fixes). The heavier machinery (formal incident command, severity matrices, comms roles, status pages) scales with blast radius and audience.
- Over-engineering for a single-operator, no-external-users system: a formal IC rotation, SEV1–SEV5 taxonomy and a public status page for a factory one person runs is ceremony. What still applies at any size is the cheap, high-value core: *detect automatically* (alerting, not luck) and *mitigate before diagnosing*. Those two are worth it even for one person; the org chart around them is not.

## How it fails
- **No detection:** nothing alerts, so the incident runs until a human notices by accident — the same bug becomes a far longer incident (proof: 245 min undetected vs 67 detected).
- **Diagnose-first:** the responder chases root cause while users keep suffering, instead of rolling back or failing over to stop impact immediately (proof: 67 min vs 7 min).
- **No clear owner:** several people act without coordination, repeating or undoing each other's changes; no one decides.
- **Severity misjudged:** a real emergency is treated as routine (slow response) or every blip pages everyone (alert fatigue — 062-alerts.md, 110-on-call.md).
- **Mitigation that loses data or masks the cause:** a "fix" that destroys evidence or data, or silences the alert without stopping the harm.
- **No handoff to learning:** the incident is resolved and forgotten, so it recurs (111-postmortems.md, 065-error-budgets.md).

## Review checklist
- [ ] **Is there automatic detection for this failure mode?** · Applies when: the diff adds a service or failure path whose outage would have real cost. · Block if: the only way the failure becomes known is a human noticing, with no alert on the signal that would show it (062-alerts.md, 058-monitoring.md).
- [ ] **Is there a fast mitigation separate from the fix?** · Applies when: the diff ships a change that could cause a production incident. · Block if: the only recovery is a forward fix (diagnose + patch + deploy), with no quick rollback, feature flag, or failover to stop user impact first (055-rollbacks.md, 051-feature-flags.md).
- [ ] **Does mitigation preserve data and evidence?** · Applies when: the diff adds a recovery/mitigation path. · Block if: the mitigation can destroy data or erase the signals a postmortem would need.
- [ ] **Is the incident process proportionate?** · Applies when: the diff adds incident-response machinery. · Block if: it imposes formal IC roles, severity taxonomies or a status page on a single-operator/no-external-user system, where automatic detection and a mitigation path are the parts that actually pay off.

## In the factory
- **The factory records incidents but does not yet detect them automatically — the known weak point.** `HEARTBEAT.md` carries `pipeline_status`, `blocking_reason` and `open_incidents`: `_finish` sets the pipeline status from a terminal run's outcome (`webhook_adapter.py:397-409`, failed/error/blocked/timeout), and a burst of rejected requests raises `open_incidents` (`:77`, `_log_rejection`). But nothing pushes those anywhere — the intended watcher (Grok Bot) "is not wired yet" (CLAUDE.md), `/heartbeat` is not even routed through the tunnel, and `/health` is liveness-only. So an incident sits in a file until the operator happens to look — exactly the "no detection" failure. Already the **Monitoring** (medium), **Dead Letter Queues** and **Health Checks** rows in GAPS.md; no new gap.
- **Mitigation exists and is fast, which is the right half to have first:** a bad merge is reverted by a PR (055-rollbacks.md), the adapter restarts under launchd `KeepAlive` (008-kubernetes.md), and runs are capped so a storm cannot run away (001-rate-limiting.md). The one place mitigation is *blocked* is a gate-breaking merge (`enforce_admins` with no break-glass) — the Rollbacks row.
- **Severity and IC roles are rightly absent:** one operator, no external users. A SEV matrix and comms roles would be ceremony. The cheap core — mitigate-first, and (once wired) alert-on-detect — is what matters.
- Not applicable at today's load: incident commander rotation, severity taxonomy, status page, comms lead.

## Proof
`python3 knowledge/systems/proofs/109_incidents.py`, the impact timeline of one incident under three responses (minutes of user-facing impact):
```
customer-impact minutes per response to the same incident:
  undetected (no alerting)      245 min  #################################################
  detected, diagnose-first       67 min  #############
  detected, mitigate-first        7 min  #
```
The same underlying bug costs 245, 67, or 7 minutes of user impact depending only on the response. Detection collapses 245→67 (an alert instead of luck); mitigating before diagnosing collapses 67→7 (roll back to stop impact, root-cause afterward). The eventual fix is identical in all three — the timeline is what decides the damage.

## Related
110-on-call.md, 111-postmortems.md, 062-alerts.md, 058-monitoring.md, 055-rollbacks.md, 051-feature-flags.md, 065-error-budgets.md

## Sources
- "Managing Incidents", Google SRE Book, ch. 14: https://sre.google/sre-book/managing-incidents/
- "Incident Response", PagerDuty: https://response.pagerduty.com/
