# 21. Cron Jobs

Track: F. Async and messaging · Status: proven · Updated: 2026-10-19

## What it is
A cron job runs work on a schedule ("every day at 03:00", "every 5 minutes") instead of in response to a request: cleanups, syncs, reports, renewals, backups. The scheduler only decides when to start a run. Everything else is the job's problem:
- **Overlap:** a run that outlasts the interval overlaps the next. Kubernetes' default `concurrencyPolicy` is `Allow`; `Forbid` skips the new run, and `Replace` kills the old one.
- **Missed runs:** classic cron skips runs while the machine is asleep. macOS launchd instead "will start the job the next time the computer wakes up", coalescing several missed intervals into one.
- **Duplicates:** Kubernetes says a CronJob may create "two Jobs" or "no Job", "therefore, the Jobs that you define should be idempotent."
- **Time zones:** schedules in local time hit daylight-saving gaps and repeats.

A good cron job is idempotent, bounded in time, protected against overlap, scheduled in UTC, and monitored for "did not run", not only for "failed".

## When it is worth it
A schedule is worth it for work with no natural trigger (expiry, retention, reconciliation, periodic reports), or work that must happen even when nothing else does. When an event already marks the right moment (a run finishing, a file arriving), doing the work then is simpler and fresher than polling for it on a schedule. In-process timers suit periodic work that belongs to one long-running service and should die with it. A separate scheduler is for work that must run whether or not any service is up. Distributed schedulers with leader election are for fleets.

## How it fails
- **Overlapping runs:** a job takes longer than its interval → two copies race on the same data, losing updates or doing the work twice.
- **Silent non-run:** the scheduler, host or job is down, or the job exits early → nothing alerts, because only failures were monitored.
- **Local-time schedule across daylight saving:** a 02:30 job meets a day with no 02:30, and a 01:30 job meets a day with two → it runs late, never, or twice.
- **Thundering herd at :00:** many jobs (or many hosts) fire at the same minute → load spikes.
- **Not idempotent:** the scheduler's occasional duplicate, or a manual re-run, repeats a side effect.
- **Unbounded run:** a stuck job holds its lock forever, and every later run skips.

## Review checklist
- [ ] **Can two runs of the job overlap?** · Applies when: the diff adds or changes a scheduled job or periodic timer. · Block if: a run can outlast the interval and there is no lock, skip-if-running policy (`Forbid`) or single-runner guarantee.
- [ ] **Is the job idempotent and bounded?** · Applies when: the diff adds a scheduled job with side effects. · Block if: a duplicate or repeated run repeats a side effect, or the run has no timeout.
- [ ] **Is the schedule in UTC?** · Applies when: the diff sets a calendar schedule (cron expression, `StartCalendarInterval`, `schedule:`). · Block if: it is in a local zone that observes daylight saving, at a time inside the transition window, with no explicit time zone.
- [ ] **Would a missed run be noticed?** · Applies when: the diff adds a job whose absence matters (backups, retention, renewals). · Block if: nothing alerts when it has not succeeded within its expected interval.
- [ ] **Is a schedule the right trigger?** · Applies when: the diff adds a periodic job. · Block if: an existing event (a run finishing, a startup, a request) already marks when the work is needed, and polling on a timer only adds delay and load.

## In the factory
- The factory has no cron jobs and no scheduled workflows. `.github/workflows/*.yml` trigger only on `pull_request` and `pull_request_target`.
- Its one periodic task is in-process and is right:
  - `factory/intake/webhook_adapter.py:157-162` (`_stamp_alive`) stamps `alive_at` every 60 s (`:84`), in UTC (`time.gmtime`);
  - it waits on `threading.Event.wait`, a monotonic timeout, so wall-clock jumps do not bunch or skip stamps;
  - it cannot overlap itself, because there is one thread;
  - `_set_heartbeat` catches its own exceptions (`:546-547`), so one failed write does not kill the loop.
- Retention runs on an event, not a schedule: `_recover` prunes runs older than 30 days at each start (`:715-732`). That is acceptable, since the adapter restarts on every deploy and the run logs average 421 KiB. If uptime ever grows past the 30-day retention, move pruning onto the existing 60 s timer. The launchd stdout and stderr logs (`.factory-logs/intake.*.log`, 638 KB today) are not rotated by anything; that is part of the Logging row in GAPS.md.
- Not applicable at today's load: a scheduler, `concurrencyPolicy`, leader election and job monitoring.

## Proof
`python3.11 -I knowledge/systems/proofs/021_cron.py`. A is a scheduler that fires a real process every 0.5 s. Each run does a 1.2 s read-modify-write on a shared state file. B uses `zoneinfo` for this host's zone, America/New_York:
```
A  no lock             : 8 runs, 0 skipped, peak concurrent 3, counter 3 (should equal runs: 8)
A  flock, skip if busy : 3 runs, 5 skipped, peak concurrent 1, counter 3 (should equal runs: 3)
B  daily 02:30 on 2026-03-08: 02:30 does not exist; it resolves to 03:30 EDT (the job runs at the wrong time, or is skipped by cron)
B  daily 01:30 on 2026-11-01: 01:30 happens twice, at 05:30 and 06:30 UTC (a run per occurrence = twice)
B  in UTC: 06:30 UTC every day exists exactly once on both dates
```
Overlap lost 5 of 8 updates. The skip-if-busy lock lost none. How a given cron daemon handles the missing hour varies; that is the reason to schedule in UTC. The launchd behaviour on sleep is quoted from `man launchd.plist` on this machine.

## Related
014-idempotency.md, 037-pessimistic-locking.md, 039-race-conditions.md, 011-timeouts.md, 058-monitoring.md, 096-clock-skew.md

## Sources
- "CronJob" (concurrency policy, limitations, time zones), Kubernetes documentation: https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
- `launchd.plist(5)`, macOS manual page (StartCalendarInterval, behaviour on sleep), read locally with `man launchd.plist`
