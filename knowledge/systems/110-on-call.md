# 110. On-Call

Track: L. Operations · Status: proven · Updated: 2026-10-19

## What it is
On-call is the arrangement by which someone is responsible, at a given time, for responding to production incidents (109-production-incidents.md) — carrying the pager, acknowledging alerts, and either mitigating or escalating. A healthy on-call rests on a few principles from the SRE practice: **pages must be actionable** (every page needs a human to do something now; if not, it should be a ticket or a dashboard, not a page), **the load must be sustainable** (Google caps on-call at roughly two incidents per shift so each gets real attention, and limits operational load to ~50% of an SRE's time), there must be a clear **escalation path** (if the primary cannot handle or does not respond, it goes to a secondary or the owner), and the responder needs **runbooks and authority** to act. The failure this card proves is **alert fatigue**: when most pages are noise, the responder learns to distrust the pager, and the one real page is answered slowly or missed — the boy-who-cried-wolf effect, plus burnout from the sheer volume.

## When it is worth it
- A formal rotation is worth it once a system has users who feel outages at any hour and a team large enough to share the burden without burning anyone out. Then rotations, escalation policies, paging tools (PagerDuty/Opsgenie) and compensation matter.
- Over-engineering for a single-operator, no-external-user system: there is no rotation to build, no escalation tier, no 3 a.m. SLA. What still transfers at any size is **alert hygiene** — page only on actionable, symptom-level signals (an SLO burn, "the factory can't deliver"), and route everything else to a log or dashboard. The discipline of "is this worth interrupting a human?" is the valuable part; the rotation machinery is not.

## How it fails
- **Alert fatigue / cry-wolf:** noisy, low-precision paging trains the responder to ignore pages, so the real one is slow or missed, and the volume burns the person out (proof: 2% precision, 9 pages/shift, ~29 min to ack the real page vs 2 min when tuned).
- **Unsustainable load:** too many pages per shift (or too few people in the rotation) means no time to handle each properly, and cascading fatigue (058-monitoring.md, 062-alerts.md).
- **No escalation path:** the primary misses a page and nothing re-routes it, so a real incident sits unacknowledged.
- **Non-actionable pages:** alerts that need no human action (a transient blip, an informational event) page anyway, diluting signal.
- **No runbook or authority:** the responder is paged but lacks the documented steps or the access to mitigate, so time is lost figuring out what to do (109: mitigate-first needs a known lever).
- **Paging on causes, not symptoms:** alerting on every internal cause produces many pages for one user-visible problem; page on the symptom (SLO/user impact) instead.

## Review checklist
- [ ] **Is a new alert actionable and symptom-level?** · Applies when: the diff adds an alert that pages a human. · Block if: a human cannot act on it immediately, or it fires on an internal cause rather than user-visible impact — it belongs in a ticket or dashboard, not the pager (062-alerts.md).
- [ ] **Could this change raise page volume past a sustainable rate?** · Applies when: the diff adds alerting or a failure mode that could page repeatedly. · Block if: a single underlying problem can emit many pages (no grouping/dedup/rate-limit), risking fatigue.
- [ ] **Is there an escalation path if the page is unacknowledged?** · Applies when: the diff sets up paging for a system with real users. · Block if: a missed page has no secondary/timeout escalation, so a real incident can sit unanswered.
- [ ] **Is an on-call rotation proportionate here?** · Applies when: the diff introduces rotation/paging machinery. · Block if: it builds a rotation and escalation tiers for a single-operator or no-external-user system, where actionable-alert hygiene is the part that pays off.

## In the factory
- **There is no rotation, and there should not be: one operator is the whole "rotation."** No external users feel a 3 a.m. outage, so escalation tiers and a SLA would be ceremony. Building them would be the textbook over-engineering.
- **The part that does transfer — alert hygiene — is mostly unbuilt, and already recorded.** The adapter writes incident signal into HEARTBEAT (`open_incidents`, `pipeline_status`) but nothing pages the operator: the watcher "is not wired yet" (CLAUDE.md), `/heartbeat` is not routed through the tunnel, and there is no alert on `alive_at` going stale. That is the **Monitoring** gap (medium) in GAPS.md — stated there as "route `/heartbeat` for Grok Bot … and have it alert when `alive_at` goes stale." On-call's lesson sharpens *what* that one alert should be: a single actionable, symptom-level page ("the factory can't deliver / is down"), not a stream of low-precision notifications. No new gap; this is the On-Call framing of the Monitoring gap.
- **Good hygiene already present:** the burst flag only raises an incident at `REJECTION_BURST = 20` rejected requests in a window (`webhook_adapter.py:77`), not on every single rejection — precisely the "don't page on every blip" rule, applied to the one incident signal the factory has.
- Not applicable at today's load: PagerDuty/Opsgenie, rotation schedules, escalation policies, on-call compensation.

## Proof
`python3 110_oncall.py`, the same real incidents under two alerting configs, with responder fatigue modelled as acknowledgement delay growing per preceding false page:
```
noisy (alert on every blip)        precision   2%   9.0 pages/shift  real-page ack ~  29 min  BURNOUT + cry-wolf
tuned (symptom / SLO-burn only)    precision  67%   0.4 pages/shift  real-page ack ~   2 min  sustainable
```
With the same underlying incidents, noisy paging drowns the real page in false ones (2% of pages actionable) so it is acknowledged ~29 minutes late and the shift load (9 pages) is unsustainable; tuned, symptom-level paging reaches 67% precision, under one page per shift, and the real page is answered in ~2 minutes. Alert quality, not alert quantity, is what makes on-call work.

## Related
109-production-incidents.md, 062-alerts.md, 063-slos.md, 058-monitoring.md, 064-slis.md, 065-error-budgets.md, 111-postmortems.md

## Sources
- "Being On-Call", Google SRE Book, ch. 11: https://sre.google/sre-book/being-on-call/
- "On-call" and alerting philosophy, Google SRE Workbook: https://sre.google/workbook/alerting-on-slos/
