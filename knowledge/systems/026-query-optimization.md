# 26. Query Optimization

Track: G. Data · Status: proven · Updated: 2026-10-19

## What it is
Query optimization is making a data request do less work: read fewer rows, touch fewer pages, make fewer round trips. The tool is the query plan. `EXPLAIN` shows the planner's chosen tree and its estimates, and `EXPLAIN ANALYZE` runs the query and adds actual rows and times. Postgres's docs say the thing "most important to look for is whether the estimated row counts are reasonably close to reality". A large gap means bad statistics and, usually, a bad plan.

The recurring wins:
- **Seek, don't scan:** an index the predicate can use (025-database-indexing.md).
- **Keyset pagination instead of `OFFSET`:** `OFFSET n` must read and discard n rows, so deep pages get slower and rows shift when data is inserted. Seek pagination (`WHERE (queued_at, id) < (?, ?) ORDER BY ... LIMIT 20`) jumps straight to the page and needs a unique tiebreaker.
- **Fetch only what is used:** the columns and rows the caller needs.
- **One set-based query instead of many small ones:** see 027-n-plus-one-queries.md.

How a query is written matters much less than whether its plan can use an index. A correlated subquery and a join often compile to the same index lookups.

## When it is worth it
Optimize a query when it is on a request path or runs often, and measurement shows it matters: slow-query logs, `EXPLAIN ANALYZE`, or p95 latency. Start from the plan, not from rewriting syntax. Deep `OFFSET` pagination, missing indexes behind per-row subqueries, and over-fetching are worth fixing as soon as tables grow past what fits in a quick scan. Rewriting queries that run once a day over small tables, or chasing cost units without a latency problem, is over-engineering.

## How it fails
- **Deep `OFFSET` pagination:** page 50,000 reads and throws away a million rows on every request → latency grows with the page number, and concurrent inserts make pages skip or repeat.
- **Per-row subquery without an index:** a correlated subquery over an unindexed column runs one full scan per outer row → the cost is outer rows × table size.
- **Optimizing from syntax instead of the plan:** a "faster" rewrite produces the same plan, while the real cause (a missing index, stale statistics) stays.
- **Estimates far from actuals:** stale or missing statistics → the planner picks a nested loop over millions of rows, or the wrong index.
- **Over-fetching:** `SELECT *`, or every row of a table, when the caller shows twenty → wasted I/O, memory and transfer on every call.
- **Testing on toy data:** the plan on 100 rows (a scan, correctly) is not the plan on 10 million.

## Review checklist
- [ ] **Has the new hot query's plan been checked at realistic size?** · Applies when: the diff adds or changes a query on a request path or in a frequent job, against a table expected to exceed a few thousand rows. · Block if: no plan or timing at realistic volume shows that it seeks (not scans) the large table.
- [ ] **Is pagination keyset-based where pages can be deep?** · Applies when: the diff adds paginated listing over a growing table. · Block if: it uses `OFFSET` for pages that can go deep, or orders by a non-unique column with no tiebreaker.
- [ ] **Does each per-row subquery or lookup hit an index?** · Applies when: the diff adds a correlated subquery, or a join evaluated per row. · Block if: the inner lookup's column has no index, so each outer row scans the inner table.
- [ ] **Does the query fetch only what the caller uses?** · Applies when: the diff adds a query or remote fetch feeding an API response or a page. · Block if: it selects whole rows or all records when the caller uses a few columns or a page, on a table or result set that can grow large.
- [ ] **Is the optimization measured?** · Applies when: the diff rewrites a query for speed. · Block if: there is no before-and-after plan or timing showing a real gain on a path where latency matters.

## In the factory
- There is no SQL. The adapter's "queries" are a full scan of run records (`_runs()`, `factory/intake/webhook_adapter.py:216-217`; sized in 025-database-indexing.md) and GitHub lookups for the dashboard (`_pr`, `:658-672`, called from `command_data`, `:691-712`).
- The dashboard needs every run: its header counts all runs and all merged PRs (`factory/intake/command.html:237-239`), so returning them all is not over-fetching.
- The PR lookups are already shaped by measurement. Right:
  - merged and closed PRs are cached for good, and open ones for 60 s (`PR_CACHE_TTL`, `:646`), so a warm cache makes no `gh` calls while no PR is open (0 open today);
  - a cold cache fetches each PR with 8 threads. On the 8 real PRs that took 1.55 s, against 3.85 s sequentially and 2.24 s for one batched `gh pr list --limit 100`, which also pulled 49 PRs nobody asked for (proof C).
  - Batching wins only past roughly a hundred PRs per cold load. That shape belongs to 027-n-plus-one-queries.md.
- Not applicable at today's load: query plans, keyset pagination and statistics maintenance. There is no database, and at most 900 run records.

## Proof
`python3.11 -I scratchpad/mastery/026_queries.py` (SQLite 3.53.1, 1,000,000 runs, 3,000,000 events):
```
A  page      1: OFFSET     0.11 ms   keyset   0.01 ms   same rows: True
A  page   1000: OFFSET     0.08 ms   keyset   0.01 ms   same rows: True
A  page  50000: OFFSET     4.12 ms   keyset   0.01 ms   same rows: True
B  correlated, indexed                  0.9 ms  [... CORRELATED SCALAR SUBQUERY 1 | SEARCH e USI...]
B  grouped join, indexed                1.2 ms  [... SEARCH e USING COVERING INDEX events_run ...]
B  correlated, NO index (20 runs)     874.3 ms  [... CORRELATED SCALAR SUBQUERY 1 | SCAN e]
```
- A: `OFFSET` cost grows with depth (even on a covering index), while seek stays constant and returns the same rows.
- B: with an index, the subquery and the join run the same plan; without one, 20 outer rows cost 20 full scans.

C runs the real GitHub API read-only, on the 8 PRs referenced by `.factory-logs`:
```
C  8 PRs, one gh pr view each, sequential:  3.85 s (0.48 s per call)
C  8 PRs, one gh pr view each, 8 threads:   1.55 s
C  one gh pr list --limit 100 (same fields):    2.24 s, covers 8/8 of them plus 49 more
```

## Related
025-database-indexing.md, 027-n-plus-one-queries.md, 002-caching.md, 091-latency.md, 043-thread-safety.md

## Sources
- "Using EXPLAIN", PostgreSQL documentation: https://www.postgresql.org/docs/current/using-explain.html
- "We need tool support for keyset pagination" (no-offset), Markus Winand, Use The Index, Luke: https://use-the-index-luke.com/no-offset
