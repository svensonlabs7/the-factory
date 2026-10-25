# 102. API Versioning

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

Triggers: files `^factory/intake/command\.html$` · lines `@app\.(get|post|put|patch|delete)|/command/data|JSONResponse|response_model`

## What it is
API versioning lets an API change without breaking the clients already using it. The first rule is to avoid needing a new version.

**Additive changes are compatible:** a new endpoint, a new response field that was never there before, a new optional parameter.

**Breaking changes need a new version:** renaming or removing a field, changing its type or meaning, making a parameter required, changing error codes or semantics.

The common schemes:
- a version in the path (`/v1/...`);
- a version in a header or media type;
- date-based versions pinned per client. Stripe pins each account to the version of its first request, and transforms responses backwards through "version change modules".

Every supported version is code to maintain. So retiring one is part of the scheme: announce deprecation, send the `Sunset` header (RFC 8594) with the retirement date, then remove it.

## When it is worth it
Versioning is worth it when an API has clients you do not deploy: external customers, other teams' services, mobile apps, a separately released bot. Without that, an API changed in the same commit as all its callers needs no version, only a single deploy. Formal versioning is over-engineering until the first external client exists. The discipline that always pays is additive-only change to anything another program reads.

## How it fails
- **Silent breaking change:** a field is renamed or retyped in place → every client written against the old name breaks at once, often as `KeyError` or `undefined` instead of an error from the API.
- **The schema lives somewhere unexpected:** the response shape is derived from a template, a database column or a config file → an innocent-looking edit there is a breaking API change, and no API test notices.
- **Dead fields that look alive:** a field stays in the response with a placeholder value nobody updates → clients trust a constant (`queue depth 0`) as a live reading.
- **Versions never retired:** v1 to v5 are all maintained → the cost grows with every change, and fixes must be applied five times.
- **Version checks scattered through the code:** `if version < X` branches all over the handlers, instead of a single transformation layer.
- **No deprecation signal:** a version is removed without `Deprecation` or `Sunset` notice → clients learn of it from the outage.

## Review checklist
- [ ] **Is every change to a response or request additive?** · Applies when: the diff changes an endpoint's request or response shape, or the source the shape is derived from (template, model, column). · Block if: it renames, removes or retypes an existing field, or makes a parameter required, on an API with clients deployed separately, with no new version or transition period.
- [ ] **Is the contract pinned by a test that reads the real source?** · Applies when: the diff adds or changes an endpoint that another program consumes. · Block if: the only test builds its own fixture of the shape, so an edit to the real source would pass.
- [ ] **Does every field carry a live value?** · Applies when: the diff adds or exposes a response field. · Block if: nothing writes it, so it always returns a placeholder.
- [ ] **Is retirement announced?** · Applies when: the diff removes an endpoint, field or version that external clients use. · Block if: there was no deprecation notice or `Sunset` date first.
- [ ] **Is a versioning scheme needed at all?** · Applies when: the diff adds `/v1` paths, version headers or version transformation code. · Block if: every client ships in the same deploy as the API.

## In the factory
- The adapter's endpoints (`factory/intake/webhook_adapter.py:588-691`) are unversioned. That is right today:
  - the only routed clients are the operator's dashboard (`/command`, `/command/data`), which ships in the same deploy, and the signed `/trigger` sender, which is not yet wired (`infra/cloudflare-tunnel/config.yml:6,9`);
  - `/trigger` already accepts additive sender fields (082-schema-versioning.md).
- `/heartbeat` (`:639-642`) is the API meant for an external watcher, Grok Bot. Its schema is the row names of `HEARTBEAT.template.md`:
  - renaming a row there is a breaking API change, and it is a markdown edit;
  - no test reads the real template, because `tests/test_adapter.py:140,958` builds its own table, so such a rename passes every check (proof B);
  - adding a row instead keeps old clients working (proof C).

  Today the template has a row for every field the adapter writes (proof A).
- Dead fields in that same API: `intake_queue_depth` and `last_pr_merged` are never written, so `/heartbeat` always returns `0` and `—`. This is already in GAPS.md, under Backpressure. Removing them is free now and a breaking change once a client reads them.
- When Grok Bot is wired, the second and third checklist items apply: pin the field set with a test that reads the real template, and write or delete the dead fields first. `/heartbeat` is not routed through the tunnel yet (the Monitoring row in GAPS.md).
- Not applicable at today's load: version paths, version headers, Stripe-style transformation modules and `Sunset` headers. There is no external client.

## Proof
`pytest -s knowledge/systems/proofs/102_api_versioning.py`. A reads the real template and adapter source. B and C run the real adapter through `tests/test_adapter.py`'s fixture:
```
A  real template rows: 10; fields the adapter writes: ['alive_at', 'blocking_reason', 'build_status', 'last_run', 'open_incidents', 'pipeline_status', 'qa_gate_status']; missing from the template: []
B  today:              v1 client -> gate passed, pipeline completed
B  row renamed:        v1 client -> KeyError 'qa_gate_status'; fields now ['gate_status']; adapter logged: ['HEARTBEAT.md has no qa_gate_status row']
C  row added instead:  v1 client -> gate passed, pipeline completed
```
The live adapter's `/heartbeat` returned `intake_queue_depth: '0'` and `last_pr_merged: '—'`, the template defaults, while `last_pr_blocked`, which is written, held a real PR URL.

## Related
082-schema-versioning.md, 103-semantic-versioning.md, 081-database-migrations.md, 058-monitoring.md, 044-backpressure.md

## Sources
- "APIs as infrastructure: future-proofing Stripe with versioning", Stripe engineering blog: https://stripe.com/blog/api-versioning
- RFC 8594, "The Sunset HTTP Header Field": https://www.rfc-editor.org/rfc/rfc8594.html
