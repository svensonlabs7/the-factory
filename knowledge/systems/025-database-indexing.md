# 25. Database Indexing

Track: G. Data · Status: proven · Updated: 2026-10-19

## What it is
An index is a sorted copy of one or more columns, with pointers back to the rows. It turns a lookup from a full table scan (read every row, O(N)) into a tree search (O(log N)). SQLite's planner docs put it at "about 1 million times faster" for 10 million rows.

How an index gets used follows from its sort order:
- A composite index on `(a, b)` is sorted by `a`, then by `b` within each `a`. It serves `WHERE a = ?` and `WHERE a = ? AND b > ?`, but not `WHERE b > ?` alone. Hence SQLite's advice that a schema "should never contain two indices where one index is a prefix of the other."
- A covering index, one that holds every column a query needs, skips the table lookup.
- An index whose order matches `ORDER BY` skips the sort.
- Wrapping the column in a function (`lower(email) = ?`) hides it from a plain index. An expression index on `lower(email)` fixes that.

Indexes are not free. Postgres: "after an index is created, the system has to keep it synchronized with the table. This adds overhead to data manipulation operations." By default, building one on a large table blocks writes until it finishes, unless it is built `CONCURRENTLY`.

## When it is worth it
Index the columns that frequent queries filter, join or sort on, once the table is large enough for a scan to show up in latency, and confirm it with the query plan (`EXPLAIN`). Every index slows writes and takes space, so tables with heavy write traffic, and columns no query uses, should not get one. Below a few thousand rows, or for data scanned rarely, a full scan is fine and an index is over-engineering. For data that is not in a database, an in-memory map keyed by the lookup field is the index, and it is worth building only when a measured scan becomes slow.

## How it fails
- **Missing index on a hot lookup:** a query by an unindexed column scans the whole table → latency grows linearly with the data, and the database's CPU goes with it.
- **Wrong column order:** a composite index leads with a column the query does not constrain → the index is scanned or ignored.
- **Function on the column:** `WHERE lower(email) = ?`, implicit casts, `LIKE '%x'` → a full scan despite the index.
- **Too many indexes:** every insert and update maintains all of them → writes slow down (proof D: 6.7 times slower with four), and unused indexes waste space.
- **Blocking index build:** `CREATE INDEX` on a large live table without `CONCURRENTLY` → writes stop until the build ends (081-database-migrations.md).
- **Stale statistics:** the planner misjudges how selective a column is and picks a scan, or the wrong index.

## Review checklist
- [ ] **Is every new frequent lookup backed by an index?** · Applies when: the diff adds a query that filters, joins or sorts on a table expected to hold more than a few thousand rows. · Block if: the column has no usable index and the query plan shows a full scan on a request path.
- [ ] **Does the index match how the query uses it?** · Applies when: the diff adds a composite or expression index, or a query meant to use one. · Block if: the leading column is not constrained by the query, or the query wraps the column in a function or cast that the index does not cover.
- [ ] **Is each new index worth its write cost?** · Applies when: the diff adds an index. · Block if: no query in the diff or codebase uses it, it duplicates the prefix of an existing index, or the table is write-heavy and the gain is not measured.
- [ ] **Is the index built without blocking writes?** · Applies when: the diff creates an index on an existing large table in a live database. · Block if: it does not use a non-blocking build (`CREATE INDEX CONCURRENTLY` or the engine's equivalent) or a maintenance window.
- [ ] **Is the scan actually slow?** · Applies when: the diff adds an index or an in-memory lookup structure. · Block if: the data is small (hundreds of rows) and no measurement shows the scan matters.

## In the factory
- The factory has no database. Its "table" is the run records, one `.meta.json` per run. `_runs()` (`factory/intake/webhook_adapter.py:216-217`) reads and parses all of them on every `/trigger` (`_check_capacity`, `:230`, on the event loop) and every dashboard poll (`/command/data`, `:694`). That is a full scan, and it is right at this size:
  - about 0.5 ms for the 30 records of a typical month;
  - 17 ms at the ceiling that retention allows (30 days × 30 runs a day = 900 records);
  - 198 ms at 9,000 records, which would stall the event loop on each `/trigger` (proof E).

  If retention or volume grows past about 1,000 records, keep a count in memory, or move the records to SQLite with an index on `(status, queued_at)`.
- Not applicable at today's load: databases, indexes and query plans.

## Proof
`pytest -s scratchpad/mastery/025_indexing.py` (Python 3.11's `sqlite3`, 1,000,000 rows. E uses the real adapter through `tests/test_adapter.py`'s fixture):
```
A  no index:                18.71 ms  [SCAN runs]
A  index on run_id:          0.02 ms  [SEARCH runs USING INDEX runs_run_id (run_id=?)]
B  WHERE status=?:           0.06 ms  [SEARCH runs USING COVERING INDEX runs_status_time (status=? AND queued_at>?)]
B  WHERE queued_at>? only:   16.21 ms  [SCAN runs USING COVERING INDEX runs_status_time]
C  lower(email)=?:          69.24 ms  [SCAN runs]
C  + expression index:       0.02 ms  [SEARCH runs USING INDEX runs_email_lower (<expr>=?)]
D  200k inserts, 0 indexes:     61 ms
D  200k inserts, 4 indexes:    408 ms
E     30 run records: _capacity(_runs())    0.54 ms per /trigger (on the event loop)
E    900 run records: _capacity(_runs())   17.16 ms per /trigger (on the event loop)
E   9000 run records: _capacity(_runs())  197.77 ms per /trigger (on the event loop)
```

## Related
026-query-optimization.md, 081-database-migrations.md, 091-latency.md, 057-liveness-readiness-probes.md, 002-caching.md

## Sources
- "Query Planning", SQLite documentation: https://www.sqlite.org/queryplanner.html
- "Indexes: Introduction", PostgreSQL documentation: https://www.postgresql.org/docs/current/indexes-intro.html
