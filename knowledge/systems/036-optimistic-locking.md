# 36. Optimistic Locking

Track: D. Concurrency and correctness · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\betag\b|if-match|compare.?and.?(set|swap)|--force-with-lease|git push|os\.replace|optimistic`

## What it is
Optimistic locking lets everyone read and work without holding a lock, and checks for conflicts only at write time: "save this only if it is still the version I read". The record carries a version number, timestamp or content hash. The write is a compare-and-swap. If someone else changed the record in the meantime, the write is refused, and the writer must re-read, re-apply and try again (or ask a human to merge).

HTTP does this with `ETag` plus `If-Match`, refusing a stale write with `412 Precondition Failed`. Databases do it with `UPDATE ... WHERE version = :read_version` and a check of the affected row count. Git does it on every non-forced push: the remote accepts it only if your commit builds on its current head. `--force-with-lease` makes the expected value explicit. Optimistic locking suits low contention. Pessimistic locking (037-pessimistic-locking.md) suits high contention, or work too costly to redo.

## When it is worth it
It is worth it for any record that more than one actor can edit with a gap between read and write: edit forms, API resources, config documents, branches and refs, shared files. It is cheap (one version field and a conditional write), and it turns silent lost updates into explicit conflicts. Merge or conflict-resolution UIs and CRDTs are for real collaborative editing. Most systems need only "reject and re-read".

## How it fails
- **No version check:** two editors read version 1 and both save → the second silently erases the first (lost update).
- **A check without atomicity:** read the version, compare in code, then write in a separate step → a concurrent write slips between them (see 039-race-conditions.md).
- **Force by default:** `git push --force`, or "last write wins", is used to get past a rejection → the other actor's work is erased.
- **Refusal without a path forward:** the 412 or rejected push is shown as a generic failure, so users retry blindly or give up.
- **High contention:** many actors fight over one hot record → most writes are refused and retries thrash, so a queue or lock is needed instead.

## Review checklist
- [ ] **Does an update to a shared record check the version it read?** · Applies when: the diff adds an update or replace of a record, document or file that more than one actor can edit. · Block if: it writes unconditionally (no version, ETag or expected-value check).
- [ ] **Is the check and the write one atomic operation?** · Applies when: the diff implements a version check. · Block if: the comparison happens in application code before a separate write, instead of in the write itself (`WHERE version = ?`, `If-Match`, compare-and-swap).
- [ ] **Are force pushes and overwrite modes kept out of automation?** · Applies when: the diff pushes refs, uploads or replaces objects automatically. · Block if: it uses `--force` (or an overwrite flag) where `--force-with-lease` with an expected value, or a plain push, would do.
- [ ] **Does a refused write lead somewhere sensible?** · Applies when: the diff handles a version conflict. · Block if: the conflict is swallowed, retried blindly without re-reading, or reported without saying it was a conflict.

## In the factory
- `factory/intake/webhook_adapter.py:350` (`_push`): `git push origin <head>:refs/heads/<branch>`, with no force anywhere in the adapter. Each push is a compare-and-swap on the remote branch: if a human commits to a factory branch during a round, the adapter's push is rejected and the human's commit is kept (proof B). Right.
- `factory/intake/webhook_adapter.py:423`: each fix round clones its base from the remote branch (`base=branch`), so a human commit made between rounds is included in the next round. Right.
- When the push is rejected, the run ends `error` with git's message and the round's work is discarded. That is acceptable at today's load: it keeps the human's change and needs only a rerun.
- HEARTBEAT and run metas use a lock or a single writer (039-race-conditions.md), not versions, which is right for one process.
- Not applicable at today's load: ETags on the adapter's API and versioned meta records. Nothing outside the adapter edits them.

## Proof
`python3 -I knowledge/systems/proofs/036_optimistic.py`. A is an in-memory record. B is real git in scratch repos, with a human pushing to `factory/x` while a "fix round" works from the old head:
```
A  without version check: Alice saved; Bob saved; final text: "base + Bob's paragraph"
A  with version check: Alice saved; Bob 412 Precondition Failed (re-read and re-apply); final text: "base + Alice's paragraph"
B  adapter's plain push (as _push does): exit 1: ! [rejected] ... -> factory/x (fetch first)
B  --force-with-lease expecting the old head: exit 1: ! [rejected] ... -> factory/x (stale info)
B  --force: remote now at the adapter's commit = True; human's hotfix still on the branch = False
```

## Related
037-pessimistic-locking.md, 039-race-conditions.md, 014-idempotency.md, 038-distributed-locks.md

## Sources
- Martin Fowler, "Optimistic Offline Lock", Patterns of Enterprise Application Architecture: https://martinfowler.com/eaaCatalog/optimisticOfflineLock.html
- "If-Match", MDN (RFC 9110 §13.1.1 conditional requests): https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/If-Match
