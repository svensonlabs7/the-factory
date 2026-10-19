# 82. Schema Versioning

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

## What it is
Schema versioning is how the shape of data changes over time without breaking the code that writes or reads it: stored records, messages, API payloads, files. Two directions matter:
- **Backward compatibility:** new readers can read old data.
- **Forward compatibility:** old readers can read new data.

Schema registries name these BACKWARD, FORWARD and FULL. Each implies an upgrade order: consumers first, producers first, or either.

The working rules, from Protocol Buffers and Avro:
- adding an optional field with a default is safe;
- readers ignore and keep unknown fields;
- never reuse a field's name or number for a different meaning or type;
- removing a field means first stopping all reads of it.

When a change cannot follow those rules, a version marker stored with the data lets readers dispatch on it. An "upcaster" converts old records to the current shape at read time.

## When it is worth it
Any data that outlives the code that wrote it, or crosses a deploy boundary, needs compatible evolution. That covers records on disk, queued messages, and payloads between independently deployed services. Explicit version fields and upcasters are worth it when old data must stay readable for a long time, or when producers and consumers ship separately. When one process writes and reads short-lived data, and all its readers deploy with it, tolerant readers and additive changes are enough. A version field there is over-engineering.

## How it fails
- **Same name, new meaning or type:** a field keeps its name but changes type or unit → old records are misread silently (`NaN`, wrong dates, wrong amounts) or crash new code.
- **Strict reader:** unknown fields are rejected → every additive change by a producer breaks consumers (forward incompatibility).
- **Unknown fields dropped on rewrite:** an old reader rewrites a record without the new fields → data loss (see 055-rollbacks.md).
- **Required field added:** old producers do not send it → new consumers reject old messages (backward incompatibility).
- **No way to tell versions apart:** with no version marker, readers guess from the shape, which fails when two versions share a shape.
- **Wrong upgrade order:** producers start writing a new schema before consumers can read it.

## Review checklist
- [ ] **Does any existing field change type, unit or meaning?** · Applies when: the diff changes how a stored or transmitted field is written. · Block if: it keeps the field name while changing its type, unit or meaning, instead of adding a new field (or bumping a version that readers dispatch on).
- [ ] **Do readers tolerate unknown and missing fields?** · Applies when: the diff adds or changes a parser, model or deserializer for data another version may produce. · Block if: it rejects unknown fields, or requires a field that older producers or records do not have.
- [ ] **Is the upgrade order safe?** · Applies when: the diff changes a format between components deployed separately (a sender and a receiver, a writer and a stored-data reader). · Block if: the new format can reach a reader that cannot yet parse it.
- [ ] **Is a removed field unused everywhere first?** · Applies when: the diff stops writing or deletes a field. · Block if: any consumer, including UI code, scripts or an external watcher, still reads it.
- [ ] **Is a version field justified?** · Applies when: the diff adds schema versions, a registry or upcasters. · Block if: one process writes and reads the data, every reader deploys with it, and the data is short-lived.

## In the factory
- Gap, recorded and contained: `started_at` changed type under the same name, from an ISO string (the 4 archived runs from 2026-10-10) to epoch seconds (`factory/intake/webhook_adapter.py:497`), with no version in the record.
  - Python arithmetic on an old record raises `TypeError` (proof A).
  - The dashboard's own `duration` and `clock` (`factory/intake/command.html:166-172`) render it as `NaNh NaNm` and `Invalid Date`.
  - It is harmless today: the old records were moved to `.factory-logs/archive/`, and records are pruned after 30 days (`:79`).
  - The first checklist item is the rule that would have caught it.
- `factory/intake/webhook_adapter.py:180-183` (`TriggerPayload`, pydantic's default `extra="ignore"`): `/trigger` is forward compatible. A newer sender's extra field is accepted and ignored, while a renamed or retyped field gets a clear 422 (proof B). Right for a single sender. Note that an ignored field is silently dropped, so a sender relying on a new field must check that the adapter supports it.
- Run records, HEARTBEAT and `/command/data` have no version field. That is right at this scale: one process writes them, the only reader (`command.html`) ships with it, and records live 30 days.
- The one contract with an independently deployed reader is `/heartbeat` (`:639-642`), which Grok Bot is meant to poll. It is not wired yet. When it is, its field names become a public schema, and the third and fourth checklist items apply.
- The gate's verdict line (`.github/workflows/qa-gate.yml:66`, `PASS` or `BLOCK` as the last bold line) is an unversioned contract between the review skills and the workflow. Both ship from `main` together, so it is safe.
- Not applicable at today's load: schema registries, version fields and upcasters.

## Proof
`pytest -s scratchpad/mastery/082_schema_versions.py`. A reads a real archived record. B posts signed payloads to the real adapter through `tests/test_adapter.py`'s fixture:
```
A  v2 reader on an archived v1 record (started_at='2026-10-10T17:48:38.693607'): TypeError: unsupported operand type(s) for -: 'float' and 'str'
A  with a version field and an upcaster: age 8.3 days
B  newer sender adds a field ('priority'): (202, 'queued')  (accepted, field silently dropped)
B  newer sender renames 'task' to 'prompt': 422
B  sender changes 'branch' to a number:    422
```
The dashboard's real functions, run in `node` against an archived record and a current one:
```
old record: "2026-10-10T17:42:44.831126" -> duration NaNh NaNm | started Invalid Date
current record: 1792261713.869907 -> duration 8m 12s | started Sat 02:28 PM
```

## Related
081-database-migrations.md, 055-rollbacks.md, 102-api-versioning.md, 103-semantic-versioning.md, 054-rolling-deployments.md

## Sources
- "Updating A Message Type", Protocol Buffers language guide (proto3): https://protobuf.dev/programming-guides/proto3/#updating
- "Schema Evolution and Compatibility", Confluent Schema Registry documentation: https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html
