# 81. Database Migrations

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

Triggers: lines `(?i)alter table|drop (table|column)|\bmigrat|\.meta\.json|heartbeat\.template`

## What it is
A migration is a scripted, versioned change to stored data or its schema: add a column, rename a field, split a table, backfill values. It runs once, in order, as part of a deploy.

Migrations are hard for two reasons:
- **Code and data change at different moments.** During a deploy, and after any rollback, code that expects the old shape meets data in the new shape, or the reverse.
- **Running them takes locks.** In Postgres most `ALTER TABLE` forms take an `ACCESS EXCLUSIVE` lock. A big backfill in one transaction holds its locks until commit, and the application's own reads and writes wait behind it.

The standard technique is expand/contract (parallel change):
1. **Expand:** add the new shape alongside the old one.
2. **Migrate:** dual-write, backfill in small batches, then move the readers over.
3. **Contract:** remove the old shape only after no deployed version uses it.

Every step is compatible with the code on either side of it, so each deploy and each rollback is safe.

## When it is worth it
Any persisted state that outlives one deploy needs a migration story. That includes databases, and also files, queues and caches that a newer version reads. Expand/contract is worth it whenever old and new code can meet the data: a rolling deploy, a rollback window, or more than one reader. Batching and lock timeouts are worth it once tables are big enough that one statement holds a lock for longer than requests can wait. A one-step migration is fine when the service is stopped while it runs and nothing else reads the data, as long as the rollback path is known.

## How it fails
- **Breaking change in one step:** a column is renamed or dropped while old code still runs or remains the rollback target → old code fails on every query.
- **Long lock:** a backfill or table rewrite in one transaction → the app's writes queue behind it and time out ("database is locked", lock-wait timeouts, a pile-up of connections).
- **Writes lost between backfill and switch:** the old version keeps writing only the old field after the backfill ran → rows the new code cannot read, unless the new code dual-writes and a final backfill runs after the last old instance stops.
- **Migration coupled to the deploy:** the schema change and the code that needs it ship together → no safe order, and no safe rollback.
- **Untested on real data:** the migration works on fixtures and fails on production's nulls, duplicates or size.
- **Implicit schema with no migration path:** a file or record format changes, existing copies are never updated, and the new field silently goes missing.

## Review checklist
- [ ] **Is each step compatible with the code on both sides?** · Applies when: the diff renames, drops or retypes a column or field, or changes a stored format. · Block if: it is one step, and the previous version, still running or as the rollback target, would fail against the new shape.
- [ ] **Is the backfill batched, and are locks bounded?** · Applies when: the diff updates or rewrites many rows, or alters a large table. · Block if: it runs in one transaction over an unbounded number of rows, or takes an exclusive lock with no lock timeout, on a table the live app writes.
- [ ] **Are writes made during the transition captured?** · Applies when: the diff backfills a new field while an old version may still write. · Block if: there is no dual-write and no final backfill after the old version is gone.
- [ ] **Is the contract step separate and gated?** · Applies when: the diff drops the old column, field or format reader. · Block if: a deployed or rollback-target version still reads it.
- [ ] **Do existing copies of an implicit schema get the new shape?** · Applies when: the diff adds a field to a template, file format or config that existing installations already have a copy of. · Block if: nothing adds the field to existing copies, so the new code's writes or reads of it silently do nothing.

## In the factory
- The factory has no database. Its persisted state is JSON run records (`.factory-logs/*.meta.json`), JSONL logs and `HEARTBEAT.md`. The same rules apply to them.
- `factory/intake/webhook_adapter.py:127-129,220-224,694`: readers use `.get` with defaults, and `_update` merges, so records of an older shape still load. The 2026-10-10 format change (old `factory-YYYYMMDD-…` IDs and an ISO-string `started_at`) was contracted by moving the 4 old records to `.factory-logs/archive/`. Put back, they still serve `/command/data` and `/status` (proof C). Right.
- Gap (low): `HEARTBEAT.md` has an implicit schema and no migration path. `:86-88` copies `HEARTBEAT.template.md` only when the file is missing, so a row added to the template later never reaches the live `HEARTBEAT.md`. `_set_heartbeat` (`:535-547`) then only logs "has no … row", and `/heartbeat`, which Grok Bot is meant to poll, never shows the field (proof D; see GAPS.md). Today the live file matches the template's 10 rows, and the template has changed once (#46).
- Not applicable at today's load: migration tooling, online schema-change tools and lock tuning. There is no database. Today the template gap is the only migration risk.

## Proof
`pytest -s knowledge/systems/proofs/081_migrations.py` (SQLite 3.51 from the stdlib. C and D use the real adapter through `tests/test_adapter.py`'s fixture. C copies the real archived records):
```
A  rename in one step, old code still running: OperationalError: table runs has no column named task
A  expand/contract: old code after each step -> [('expand', 'old write'), ('backfill', 'old write')]; rows still without `prompt`: 1 (the old version's write after the backfill)
A  after the last old instance stops, a final backfill: rows without `prompt`: 0
B  backfill in one transaction: 1.1 s; app writes ok 28, failed 'database is locked' 4
B  backfill in batches of 5,000: 1.5 s; app writes ok 89, failed 'database is locked' 0
C  4 archived old-format runs back in LOG_DIR: /command/data -> 200; /status -> 200 'error'; started_at types: ['str']
D  new template row set on an existing HEARTBEAT.md: in /heartbeat False; warnings: ['HEARTBEAT.md has no gate_minutes row']
```
Postgres's `ACCESS EXCLUSIVE` behaviour is from its docs, not run here: no Postgres image is on this machine.

## Related
082-schema-versioning.md, 055-rollbacks.md, 054-rolling-deployments.md, 052-blue-green-deployment.md, 037-pessimistic-locking.md, 014-idempotency.md, 102-api-versioning.md

## Sources
- "ALTER TABLE", PostgreSQL documentation: https://www.postgresql.org/docs/current/sql-altertable.html
- "ParallelChange", Danilo Sato, martinfowler.com: https://martinfowler.com/bliki/ParallelChange.html
