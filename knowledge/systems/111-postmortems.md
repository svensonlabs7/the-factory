# 111. Postmortems

Track: L. Operations · Status: proven · Updated: 2026-10-19

## What it is
A postmortem is the written record and analysis of an incident (109-production-incidents.md) after it is resolved: what happened, the timeline, the impact, the **root cause and contributing factors**, and — the part that actually matters — a list of **action items** that remove or mitigate the cause so it cannot recur, each owned and tracked to completion. The defining practice is that it is **blameless**: it examines the systems and decisions that let the failure happen, not the person who pushed the button, on the premise that people acting reasonably with the information they had cannot be the root cause. Blamelessness is not politeness; it is what makes the analysis *honest*. If people fear blame, they hide the real cause, and the latent fault fires again (proof: the share of incidents whose true cause is actually removed is what separates a system that drains its faults from one that keeps hitting them). A postmortem without tracked action items is a story; the value is in closing the loop (065-error-budgets.md).

## When it is worth it
- Worth it after any incident with real impact, or a near-miss that easily could have had it: the cost of writing it is small against the cost of the same incident recurring. Mature practice triggers a postmortem on defined criteria (user-visible downtime over a threshold, data loss, a failed rollback) so it is routine, not a punishment.
- Over-engineering: a heavyweight templated document with a formal review meeting for a trivial, well-understood blip on a single-operator system. The cheap, high-value core scales down to any size — *write down what broke, why, and the one change that stops it, then make that change*. A standing list of known failure modes and their fixes is that core in its leanest form.

## How it fails
- **No action items, or untracked ones:** the incident is analysed and written up, but nothing changes, so the same fault recurs (proof: 40 vs 8 cumulative incidents when causes are left in place vs removed).
- **Blame instead of cause:** a person is named as the cause, the systemic gap is left, and — because blame makes people hide causes — fewer real faults are removed (proof: the ~30% "blame culture" case keeps most faults live, 32 vs 8).
- **Root cause stops too shallow:** the immediate trigger is fixed but the contributing factors (why the trigger was possible, why it was not caught) are not, so a sibling failure happens next.
- **Action items without owners or deadlines:** everyone agrees they are good; none are done.
- **No criteria for when to write one:** postmortems happen only for the most dramatic incidents, so smaller recurring faults are never addressed.
- **Written for blame-avoidance, not learning:** the document is defensive and vague, so the real timeline and decisions are lost.

## Review checklist
- [ ] **Does the fix address the root cause, not just the trigger?** · Applies when: the diff is (or claims to be) the remediation for an incident. · Block if: it patches the immediate symptom while the contributing factor that allowed it remains (010-circuit-breakers.md-style band-aids over a systemic gap).
- [ ] **Is there a tracked, owned action item, not just an explanation?** · Applies when: the diff or its description resolves an incident. · Block if: the outcome is a write-up with no concrete, owned change recorded somewhere it will be done.
- [ ] **Is a recurring or near-miss failure captured for follow-up?** · Applies when: the diff reveals or works around a latent failure mode (a race, an unhandled error, a manual workaround). · Block if: the workaround ships with nothing recording the underlying fault to fix, so it silently recurs.
- [ ] **Is the postmortem process proportionate?** · Applies when: the diff adds postmortem machinery (templates, required meetings). · Block if: it imposes heavyweight ceremony on a single-operator system where a recorded failure-and-fix list already captures the learning.

## In the factory
- **`GAPS.md` is the factory's postmortem ledger, in its leanest honest form.** Every row is exactly a postmortem's core: a failure mode, where it lives (`file:line`), the concrete scenario in which it bites, a severity, and a status — a blameless "what would break and the change that stops it", written down and tracked. The `systems-mastery` loop that produces it is effectively a *pre*-incident postmortem process: find and record the latent faults before they fire. `REVIEWS.md` plays the same role for the cards themselves (contradictions found and fixed).
- **The incident-recording hooks exist:** the Rollbacks row prescribes "note it in HEARTBEAT incidents", and `open_incidents`/`pipeline_status` capture a live incident's state (`webhook_adapter.py:397-409`, 109-production-incidents.md). What is missing is detection/alerting, not recording (the Monitoring gap).
- **Blamelessness is structurally easy here** — one operator, an autonomous agent — so the discipline that matters is the honest one this card proves: every gap row must carry a real fix, and the operator closes them (the GAPS header says exactly this: "the operator turns them into factory tasks and marks them done"). The action items are tracked by status; nothing automated closes them, which is correct for one operator and not a code defect.
- A formal templated postmortem doc with a review meeting would be over-engineering at one operator; `GAPS.md` is the right-sized version. No new gap.
- Not applicable at today's load: postmortem templates, review meetings, an incident-tracking tool, severity-triggered postmortem criteria.

## Proof
`python3 111_postmortems.py`, cumulative incidents from 8 latent faults over a horizon, varying how many have their root cause actually removed by a completed action item:
```
no postmortem (remove 0%)           : 40 cumulative incidents over 20 periods
blame culture (remove ~30%)         : 32 cumulative incidents over 20 periods
blameless + actions (remove 100%)   :  8 cumulative incidents over 20 periods
```
Same faults, same horizon; the only variable is the share of incidents whose root cause is actually removed. Remove none and every fault recurs for the whole horizon (40); remove all and each fault fires exactly once, then never (8). The blame-culture middle case keeps most faults live because hidden causes are not fixed. The write-up is worthless without the tracked action item that drains the fault.

## Related
109-production-incidents.md, 110-on-call.md, 065-error-budgets.md, 063-slos.md, 058-monitoring.md, 055-rollbacks.md, 087-chaos-engineering.md

## Sources
- "Postmortem Culture: Learning from Failure", Google SRE Book, ch. 15: https://sre.google/sre-book/postmortem-culture/
- "Blameless postmortems", Google SRE Workbook (example postmortem and action items): https://sre.google/workbook/postmortem-culture/
