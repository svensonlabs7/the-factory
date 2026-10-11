# Factory Heartbeat

Status snapshot for the autonomous factory pipeline. Updated by the intake adapter as each run progresses.
Reports are forwarded to `the-machine` for cross-system health tracking.

---

## Status Fields

| Field | Value |
|---|---|
| **last_run** | — |
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

**Cross-system reporting:** the-machine polls this file to track factory health. Do not rename or move it. If the pipeline is broken and cannot write here, report the incident directly to the-machine operator.

---

## Run Log

<!-- Per-run detail lives in .factory-logs/<run_id>.meta.json and .factory-logs/<run_id>.log -->
