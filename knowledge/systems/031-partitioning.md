# 31. Partitioning

Track: G. Data · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)\.jsonl|\brotat|retention|rejection_log_max|truncate|\bprune`

## What it is
Partitioning splits one large table into smaller pieces by a key, within one database: a time range (one partition per month), a list of values (per region), or a hash. The database, or the application, routes each row to its partition.

Two benefits follow:
- **Partition pruning:** queries that filter on the key touch only the matching partitions.
- **Cheap lifecycle operations:** Postgres's docs say dropping a partition "is far faster than a bulk operation" and "entirely avoid[s] the `VACUUM` overhead caused by a bulk `DELETE`". Retention becomes dropping the oldest partition, and old partitions can move to cheaper storage.

Partitioning is not sharding (030-sharding.md). It stays inside one database, so it does not add capacity, only locality and manageability.

Postgres is explicit about when it pays: "only when a table would otherwise be very large" (a rule of thumb is larger than the server's memory). It also warns that "dividing the table into too many partitions can also cause issues", in planning time and memory.

## When it is worth it
Partition a table when it is very large and its access and lifecycle follow one key: time-series logs, events, metrics, audit trails. Queries hit recent data, and old data expires. The partition key must appear in most queries, or pruning never happens. For small tables, or keys that queries do not filter on, partitioning adds complexity and planning cost for nothing. The same idea applies to files: one log file per day reads, rotates and expires far better than one ever-growing file.

## How it fails
- **Unbounded single table or file:** everything goes into one table or log → retention means slow bulk deletes (or none), and "recent" queries scan everything.
- **Hard cap instead of rotation:** a log that stops writing at a size limit keeps the oldest entries and drops the newest. Any "last 24 hours" view goes blind exactly when it is busy (proof B).
- **Partition key not in the queries:** every query scans every partition, which is slower than one table.
- **Too many tiny partitions:** planning time and memory grow with the partition count.
- **Uneven partitions:** one hot partition holds most writes, so partitioning by that key buys nothing.
- **Missing future partitions:** time partitions not created ahead of time → inserts fail at midnight on the 1st.

## Review checklist
- [ ] **Does growing time-ordered data have a retention mechanism that scales?** · Applies when: the diff adds a table, log or file that grows with time or traffic. · Block if: there is no retention, or retention is a bulk delete over an unpartitioned store expected to become very large.
- [ ] **Does a size cap drop the oldest, not the newest?** · Applies when: the diff bounds a log or event store by size. · Block if: reaching the bound stops new writes instead of rotating or expiring the oldest data.
- [ ] **Do the hot queries filter on the partition key?** · Applies when: the diff partitions a table or splits a log into files. · Block if: the frequent queries do not constrain the key, so no partition can be skipped.
- [ ] **Are future partitions created ahead of need?** · Applies when: the diff adds time-based partitions. · Block if: nothing creates the next period's partition before the first write needs it.
- [ ] **Is partitioning justified by size?** · Applies when: the diff introduces partitioning. · Block if: the table or log is small (well within memory) and a single store with an index or a simple rotation meets the need.

## In the factory
- The run records are already partitioned the cheap way: one file per run (`.factory-logs/<run_id>.meta.json`, `.log`, `.actions.jsonl`). Retention unlinks whole runs older than 30 days (`_recover`, `factory/intake/webhook_adapter.py:715-732`), the equivalent of dropping partitions, and the 2026-10-10 old-format runs were moved to `.factory-logs/archive/`, a cold partition. Right.
- `rejected.jsonl` is the opposite: one unpartitioned append log, capped at 5 MB (`:78`, `:569-571`) and never expired, which `_rejection_counts` (`:675-678`) reads whole on every dashboard poll.
  - Today it holds 13 lines (1.9 KB), so the cost is nothing.
  - At the cap: 40,323 lines and 44 ms of parsing per 15 s poll.
  - Once full, new rejections are not written at all. A bad-signature request made then is dropped, and the dashboard reports `last_24h {}` during an ongoing attack (proof B). The in-memory burst counter still raises the HEARTBEAT incident.
  - This is the Logging row in GAPS.md ("rotate `rejected.jsonl` instead of capping it"), now with its consequence measured. A daily file, with files older than the window deleted, fixes the read cost, the retention and the blind spot together.
- Not applicable at today's load: table partitioning, pruning and partition management. There is no database.

## Proof
`pytest -s knowledge/systems/proofs/031_partitioning.py` (Python 3.11). A uses SQLite with 1.2M rows over 12 months, one table against one table per month. B is the real adapter through `tests/test_adapter.py`'s fixture:
```
A  one month's count: whole table   35.9 ms, its partition only    0.8 ms
A  retention, drop the oldest month (100k rows): DELETE   46.2 ms, DROP partition    1.4 ms
B  rejected.jsonl at the cap (5.0 MB, 40,323 lines): _rejection_counts() 44 ms per dashboard poll
B  a bad-signature request now: logged False; dashboard last_24h {}, last_hour 0
```

## Related
030-sharding.md, 025-database-indexing.md, 059-logging.md, 075-ddos-protection.md, 084-backups.md

## Sources
- "Table Partitioning", PostgreSQL documentation: https://www.postgresql.org/docs/current/ddl-partitioning.html
- "TimedRotatingFileHandler" (time-partitioned log files, `backupCount` expiry), Python `logging.handlers` documentation: https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler
