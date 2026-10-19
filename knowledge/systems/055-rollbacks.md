# 55. Rollbacks

Track: E. Delivery and change · Status: proven · Updated: 2026-10-18

## What it is
A rollback returns a system to its last known-good version after a bad change. It is the fastest mitigation for a deploy that broke something: restore service first, then debug the change at leisure. Roll forward (shipping a fix) is the other option, but it means writing and testing new code under pressure.

A rollback is safe only if the old version still works with everything the new version left behind. The usual trap is a one-way change: the new version writes data, messages or files in a format the old version cannot read, so rolling back moves the outage instead of ending it.

The standard remedy is a two-phase deploy:
1. **Prepare:** ship a version that reads both formats but still writes the old one.
2. **Activate:** once Prepare is everywhere, ship the version that writes the new one.

Rolling back Activate lands on Prepare, which can read everything. Readers that keep unknown fields when they rewrite a record make many changes safe with no second phase at all.

## When it is worth it
Every deployable thing needs a known way back, written down and fast, in the time it takes to restart: code, config, images, schema. Two-phase deploys and upgrade-downgrade tests are worth it when a change alters persisted state, a wire protocol or a file format that another version reads. Automated rollback on health signals (canary analysis) pays off with fleets and frequent deploys. One host deployed by hand needs a short manual procedure, not automation.

## How it fails
- **One-way format change:** new code writes state the old code cannot parse → after the rollback, the old version crashes on startup or on every read.
- **Old code drops what it does not know:** the old version rewrites records without the new fields, or ignores a new status → data loss, or work stuck in a state nobody handles.
- **Rollback path runs through the broken thing:** the revert must pass a pipeline, gate or tool that the bad change broke → no way back without bypassing controls.
- **No known-good version:** unpinned dependencies or mutable images mean "the previous version" no longer builds the same (see 006-ci-cd.md).
- **Irreversible side effects:** migrations that drop columns, sent emails, external API calls → code can roll back, but the world cannot.
- **Rollback never practised:** the steps are found during the incident.

## Review checklist
- [ ] **Can the previous version read everything this version writes?** · Applies when: the diff changes the shape of persisted state, files, messages or an API response another version consumes. · Block if: the old version would fail to parse it, or would drop or mishandle new fields or values, and there is no Prepare step already deployed.
- [ ] **Do readers tolerate unknown fields and values?** · Applies when: the diff reads or rewrites persisted records. · Block if: it rejects unknown fields, drops them on rewrite, or crashes on an enum value it does not know.
- [ ] **Does one bad record stop the whole service?** · Applies when: the diff loads persisted state at startup. · Block if: a single unparseable record crashes startup instead of being skipped and reported.
- [ ] **Is the change reversible, or is the irreversible part separated?** · Applies when: the diff drops or rewrites data, runs a migration, or calls an external side effect. · Block if: the destructive step ships in the same deploy as the code that stops needing the data.
- [ ] **Is the way back known?** · Applies when: the diff changes how a service, gate or pipeline is deployed or rolled back. · Block if: it removes or invalidates the documented way back (a restart command, a pinned previous version, a break-glass step) without replacing it.

## In the factory
- `factory/intake/webhook_adapter.py:127-129` (`_update`): merges new fields into the loaded record, so unknown fields written by another version survive a rewrite. `_capacity` and `_recover` (`:220-224`, `:715-729`) read with `.get`, so missing fields do not crash. Right.
- The adapter's own rollback needs no merge. It runs from the operator's working copy, so `git checkout <good sha>` plus the documented `launchctl kickstart -k` (`factory/intake/README.md:89`) restores it in seconds. The revert PR can follow through the gate. Right, but unwritten as a procedure.
- Gap (low): `_recover` runs at import (`:732`) and calls `json.loads` on every meta file (`:102`) with no error handling. One unparseable meta file stops the adapter from starting, and launchd's `KeepAlive` restarts it into the same crash. Writes are atomic, so only a format change followed by a rollback, or a hand edit, triggers it (see GAPS.md).
- Gap (medium): the gate cannot roll itself back. `.github/workflows/qa-gate.yml:3-5` uses `pull_request_target`, which runs main's copy of the workflow and the skills. A merged change that breaks the gate (the workflow, a review skill, the pinned `claude` CLI) also reviews its own revert, and `enforce_admins: true` stops even the admin from merging past it. `factory/qa/README.md` has no break-glass steps (see GAPS.md).
- A new in-flight status added later would not be closed out by an older `_recover`. A run in that status during a rollback stays stuck and uncounted, as the proof shows. No such status exists today. The checklist's first item covers that change when it comes.
- Not applicable at today's load: automated rollback, canary analysis and upgrade-downgrade test fleets. There is one host and a manual deploy.

## Proof
`pytest -s scratchpad/mastery/055_rollback.py` (Python 3.11; B restarts the adapter's real module through `tests/test_adapter.py`'s fixture, playing the old version after a rollback):
```
A  one phase: v2 wrote compressed state, roll back to v1 -> read fails: UnicodeDecodeError
A  two phase: v1.5 deployed first, v2 wrote compressed state, roll back to v1.5 -> {'status': 'queued'}
B  unknown status after rollback restart: status still 'fixing' (not closed out), counted in flight: 0; unknown field kept on rewrite: True
B  one meta file in a new format, old version restarts -> import fails: UnicodeDecodeError in _recover -> launchd KeepAlive restarts it into the same crash
```
Not run: the gate's self-rollback trap. Proving it needs a broken gate on the real `main`. It follows from `pull_request_target` taking the workflow from the base branch, together with the live protection settings (`enforce_admins: true`, `strict: true`, read with `gh api`).

## Related
006-ci-cd.md, 051-feature-flags.md, 052-blue-green-deployment.md, 053-canary-releases.md, 054-rolling-deployments.md, 056-health-checks.md, 081-database-migrations.md, 082-schema-versioning.md

## Sources
- "Ensuring rollback safety during deployments", Amazon Builders' Library: https://builder.aws.com/content/3F04j2yRAAMBuPSPs50xwXZqg01/ensuring-rollback-safety-during-deployments
- "Reliable Product Launches at Scale", Site Reliability Engineering (Google), chapter 27: https://sre.google/sre-book/reliable-product-launches/
