# Factory Heartbeat

Status snapshot for the autonomous factory pipeline. Updated by the intake adapter as each run progresses.
Grok Bot is the intended watcher.

---

## Status Fields

| Field | Value |
|---|---|
| **last_run** | — |
| **alive_at** | — |
| **pipeline_status** | idle |
| **intake_queue_depth** | 0 |
| **build_status** | — |
| **qa_gate_status** | — |
| **last_pr_merged** | — |
| **last_pr_blocked** | — |
| **blocking_reason** | — |
| **open_incidents** | none |

---

## Reporting

This file is the factory's health signal. As a run progresses the intake adapter updates the status fields above in place.

**Cross-system reporting:** Grok Bot is meant to watch this status (not wired yet). `alive_at` is rewritten every minute while the adapter runs, so a stale value means the factory is down, not idle. Do not rename or move it. If the pipeline is broken and cannot write here, report the incident directly to the operator.

---

## Run Log

<!-- Per-run detail lives in .factory-logs/<run_id>.meta.json and .factory-logs/<run_id>.log -->
