# 27. N+1 Queries

Track: G. Data · Status: proven · Updated: 2026-10-19

## What it is
The N+1 problem is one query for a list followed by one more query per item, to fetch each item's related data. It usually hides inside lazy loading: SQLAlchemy says "for any N objects loaded, accessing their lazy-loaded attributes means there will be N+1 SELECT statements emitted." Django's docs give the same diagnosis: fetching parts of one set of data separately "is less efficient than retrieving it all in one query", especially "in a loop."

Each query pays a full round trip, so the cost grows with N times the latency, not with the data.

The fixes fetch the related data in bulk:
- one `JOIN` (`joinedload`, `select_related`);
- or one extra query with `WHERE id IN (...)` over all the parent keys (`selectinload`, `prefetch_related`).

`raiseload` turns an accidental lazy load into an error. The same shape appears with any remote API called per item: one HTTP call per row is N+1 too.

## When it is worth it
Batching is worth it wherever a loop touches related data over a network: an ORM against a database, or a client against an API. That is especially true on request paths, and anywhere N grows with the data. Detecting it is cheap: count queries per request in tests and in debug tooling. Below a handful of items, or when the per-item call is local and cached, N small lookups are fine, and batching adds complexity (IN-list limits, joining results back) for nothing.

## How it fails
- **Lazy load in a loop:** a template or serializer touches `run.events` for each of 100 runs → 101 queries, and the page's latency is 100 round trips.
- **Hidden in a helper:** a per-item function makes its own query or HTTP call, and a list endpoint calls it for each row.
- **Fine in tests, slow in production:** with a local SQLite or a mock, a round trip costs microseconds; over the network each costs milliseconds, multiplied by N.
- **Per-item API calls hit rate limits:** an N+1 against a third-party API (GitHub's 5,000 requests an hour) exhausts the quota as N grows.
- **Batch too large:** a single `IN` list of tens of thousands of keys hits parameter limits, or makes a huge query; batch in chunks (SQLAlchemy uses 500).
- **Caching masks it until it is cold:** a warm cache hides the N calls, and a restart or eviction brings them all back at once.

## Review checklist
- [ ] **Does a loop query or call per item?** · Applies when: the diff adds a loop over records that reads related data from a database or remote API, directly or through a helper, lazy relation or serializer. · Block if: N can grow with the data and the related data is not fetched in bulk (`JOIN`, an `IN` batch, eager loading, or a list API).
- [ ] **Is the query count per request bounded?** · Applies when: the diff adds a list endpoint or page, or adds a per-item query or remote call to one. · Block if: the queries or remote calls it adds grow with the number of items returned, with no batching, caching or test asserting a constant count.
- [ ] **Is a per-item remote call within its rate limit?** · Applies when: the diff calls a rate-limited external API once per item. · Block if: at the expected N and refresh rate, the calls per hour approach the provider's limit.
- [ ] **Does the cold path stay fast enough?** · Applies when: a cache hides per-item calls. · Block if: a cold cache (restart, eviction) makes the request take longer than its caller's timeout or refresh interval.
- [ ] **Is batching justified?** · Applies when: the diff replaces per-item lookups with a batch or join. · Block if: N is small and bounded and the per-item lookups are local or cached.

## In the factory
- `factory/intake/webhook_adapter.py:691-712` (`command_data`) calls `_pr` (`:658-672`) once per PR, a `gh pr view` each: an N+1 against GitHub. It is right at today's load:
  - merged and closed PRs are cached for good, so a warm dashboard makes 0 calls (proof B);
  - open PRs refetch after 60 s (`:646`), and there are 0 open today;
  - a cold cache after a restart costs 8 calls, run on 8 threads.
- Where it stops being right, scaled from proof B to the measured 0.48 s per real call:
  - Cold load at the 900-record retention ceiling: about 54 s (900 × 0.48 s / 8 threads), longer than the 15 s dashboard poll, so overlapping polls would refetch the same PRs (043-thread-safety.md).
  - Many open PRs: each costs one call a minute while the dashboard is open.
  - The batch fix is one `gh pr list --state open` (or a paged `--state all`) per refresh. It costs a constant number of calls but is slower at today's size (2.24 s against 1.55 s, 026-query-optimization.md). So it is not worth doing until open PRs or cold loads grow.
- The run records are read one file per run (`_runs()`, `:216-217`). That is local disk, not a round trip (025-database-indexing.md).
- Not applicable at today's load: ORMs, eager loading and query-count assertions. There is no database.

## Proof
`pytest -s scratchpad/mastery/027_n_plus_one.py` (Python 3.11. A is SQLite with statements counted by `set_trace_callback`, each paying a 1 ms round trip. B is the real `command_data` and `_pr`, with `_run` replaced to count `gh pr view` calls and charge 50 ms each, a tenth of the measured 0.48 s):
```
A  lazy loop (N+1)     : 101 statements,  152.3 ms, 100 runs / 494 events
A  IN batch (selectin) :   2 statements,    4.2 ms, 100 runs / 494 events
A  one JOIN            :   1 statements,    2.6 ms, 100 runs / 494 events
B   12 PRs | cold cache:  12 gh calls  0.12 s | warm, merged:   0 gh calls  0.00 s | all open, TTL passed:  12 gh calls  0.13 s
B   60 PRs | cold cache:  60 gh calls  0.45 s | warm, merged:   0 gh calls  0.01 s | all open, TTL passed:  60 gh calls  0.46 s
B  300 PRs | cold cache: 300 gh calls  2.17 s | warm, merged:   0 gh calls  0.01 s | all open, TTL passed: 300 gh calls  2.16 s
```
The same 100 runs and 494 events cost 101 statements lazily and 1 or 2 in bulk. The dashboard's calls scale with the number of PRs whenever the cache is cold or the PRs are open.

## Related
026-query-optimization.md, 025-database-indexing.md, 002-caching.md, 043-thread-safety.md, 001-rate-limiting.md, 091-latency.md, 094-tail-latency.md

## Sources
- "Relationship Loading Techniques", SQLAlchemy 2.0 documentation: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
- "Database access optimization", Django documentation: https://docs.djangoproject.com/en/stable/topics/db/optimization/
