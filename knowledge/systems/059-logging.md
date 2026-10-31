# 59. Logging

Track: C. Observability · Status: proven · Updated: 2026-10-18

Triggers: lines `\blog\.(debug|info|warning|error|exception)|logging\.|_log_action|_log_rejection|LOG_DIR|_append_jsonl`

## What it is
Logs are the time-ordered record of discrete events: a request arrived, a run started, a check failed, a login was refused. Good logs answer five questions for each event (OWASP's when, where, who, what, result):
- a timestamp in an international format;
- the service and version;
- the actor or source;
- the event and its outcome;
- an ID that ties related events together, such as a run or request ID.

Structured logs (one JSON object per line) can be searched and graphed, and are immune to log injection, because newlines and delimiters inside a field are escaped. Logs must never contain secrets, tokens or session IDs. They need a retention period (long enough to investigate, no longer) and rotation, so they cannot fill a disk. The Twelve-Factor App adds that a process should write unbuffered to stdout and let the environment route and store the stream.

## When it is worth it
Always. Every service needs timestamped, attributable logs of requests, security-relevant events and errors. The minimum is a timestamp on every line, an ID for each unit of work, structured events for anything you will search or count, no secrets, and bounded size. Central log shipping, indexing and log-based alerting pay off with several machines or services. One host is fine with local files, as long as they are rotated and timestamped.

## How it fails
- **No timestamps:** "when did this request arrive?" cannot be answered → no incident timeline, and no way to correlate with other systems.
- **No correlation ID:** events of one request or run are interleaved with others → no way to follow a single failure.
- **Log injection:** a newline in an untrusted field writes a forged entry ("Run … completed") into a plain-text log.
- **Secrets in logs:** a token in a debug line or exception message → anyone with log access has it.
- **Unbounded growth:** no rotation → the disk fills and the service fails. Or a hard cap that stops writing → the newest, most relevant events are the ones dropped.
- **Logging what you should not keep:** IPs, emails or payloads kept forever, with no use and a retention liability.

## Review checklist
- [ ] **Does every new log line carry a timestamp and an ID for its unit of work?** · Applies when: the diff adds logging, a log handler or a new process whose output is captured. · Block if: lines have no timestamp, or events about a request or run do not include its ID.
- [ ] **Is untrusted data logged in a structured or encoded form?** · Applies when: the diff logs request fields, payloads, task text, headers or model output. · Block if: untrusted text goes into a plain-text log line without encoding newlines and delimiters.
- [ ] **Are secrets kept out of logs?** · Applies when: the diff logs requests, headers, environment, exceptions or command lines. · Block if: a token, password, signature, session ID or full `Authorization` header can be written.
- [ ] **Is log size bounded without losing the newest events?** · Applies when: the diff adds a log file or a new high-frequency log line. · Block if: there is no rotation or retention, or the bound drops new entries instead of old ones.

## In the factory
- `factory/intake/webhook_adapter.py:90-91`: the adapter's own lines use `%(asctime)s [%(levelname)s]` and name the run (`Run %s ...`). Right.
- `factory/intake/webhook_adapter.py:122,136` (`_append_jsonl`, `_log_action`): per-run `actions.jsonl` and `rejected.jsonl` are JSON lines with an epoch `time`, so they cannot be injected and are easy to count. The run log `<run_id>.log` holds the agent's raw output, one section per attempt. Right.
- `factory/intake/webhook_adapter.py:79`: run logs, metas and action logs are pruned after 30 days (`RUN_RETENTION_DAYS`). Right.
- No secrets were found in `.factory-logs` (scan in 067-secrets-management.md), and the sandbox runner redacts the token in its own `docker run` output. Right.
- The adapter does not log task text in plain text (`Queued run %s: branch=%s`, where the branch is pattern-checked).
- Gap: uvicorn's own lines, including the whole access log, have no timestamps (0 of 5,874 lines), and `intake.out.log` is never rotated. `rejected.jsonl` stops growing at 5 MB by dropping new entries (see GAPS.md).

## Proof
`python3 -I knowledge/systems/proofs/059_logging.py .factory-logs/intake.out.log`:
```
A  plain text: 1 event became 2 lines; a reader sees a forged 'completed' entry: True
A  JSON line:  1 event is 1 line; the newline is escaped inside the field: True
B  intake.out.log: 5874 lines, 0 with a timestamp; 489 KB so far
B  with the dashboard open: ~5760 lines/day, ~179 MB/year, never rotated
```
Breakdown of the access log by route: `5653 GET /command/data` (the dashboard's 15 s poll), `56 POST /trigger`, `48 GET /health`. The average line is 85 bytes. No `newsyslog` entry and no rotating handler exist for these files.

## Related
061-metrics.md, 066-observability.md, 067-secrets-management.md, 060-distributed-tracing.md, 072-encryption-at-rest.md, 031-partitioning.md

## Sources
- "Logging Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- "XI. Logs", The Twelve-Factor App: https://12factor.net/logs
