# Factory Heartbeat

Status snapshot for the autonomous factory pipeline. Updated by the QA gate after each run.
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

This file is the factory's health signal. After each pipeline run the QA agent writes the updated status fields above and appends a run log entry below.

**Cross-system reporting:** the-machine polls this file to track factory health. Do not rename or move it. If the pipeline is broken and cannot write here, report the incident directly to the-machine operator.

---

## Run Log

<!-- QA agent appends one line per run: [timestamp] status | pr | notes -->
