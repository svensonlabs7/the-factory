# 84. Backups

Track: L. Operations · Status: proven · Updated: 2026-10-19

## What it is
A backup is a separate, recoverable copy of data that lets you restore it after loss — hardware failure, deletion, corruption, ransomware, a bad migration. The widely used discipline is **3-2-1**: at least three copies, on two different media, with one off-site. Two parameters frame how good a backup needs to be: **RPO** (recovery point objective — how much recent data you can afford to lose, which sets backup frequency) and **RTO** (recovery time objective — how fast you must be able to restore, which sets the backup *mechanism*). The rule that catches people is that a backup is worthless until a **restore** has been proven: a job that reports success can still produce an archive that will not restore — truncated, corrupted, missing a file, or encrypted with a lost key — and only an actual test-restore compared against the source reveals it (proof). Backups also need the same care as the data: off-site copies and retention protect against site loss and against a corruption that is itself backed up before anyone notices.

## When it is worth it
- Worth it for any data whose loss would cost more than the backup does — which is almost all stateful data. The *level* scales with value: frequent, tested, off-site, versioned backups for irreplaceable data; a single copy for data that is cheap to regenerate.
- The honest boundary is **not** "small system, skip backups" — it is *what actually needs backing up*. Data that is fully reconstructable from a source already backed up elsewhere (derived caches, re-cloneable repos, regenerable credentials) does not each need its own backup. Elaborate backup infrastructure for data that is already durable elsewhere, or trivially regenerated, is the over-engineering; losing the one copy of something irreplaceable because "the system is small" is the under-engineering.

## How it fails
- **Never restore-tested:** the backup job succeeds for months, and the archive turns out unrestorable exactly when it is needed (proof: "file exists" passes, the test-restore fails).
- **No off-site / single copy:** the backup is on the same disk or machine as the data, so the failure that loses the data loses the backup too (not 3-2-1).
- **Corruption backed up silently:** a slow data corruption is captured into every backup, and short retention means every good copy has aged out before the corruption is noticed.
- **RPO too loose:** backups are too infrequent, so a loss discards more recent work than the business can tolerate.
- **RTO not met:** the backup exists but restoring it takes far longer than the outage budget (a huge cold archive, a manual process).
- **Secrets/keys not recoverable:** data is backed up but the key to decrypt it, or a credential needed to stand the service back up, is not — so the restore cannot complete (067-secrets-management.md).

## Review checklist
- [ ] **Is the restore tested, not just the backup?** · Applies when: the diff adds or changes a backup of data whose loss matters. · Block if: success is judged by the backup job completing or the archive existing, with no periodic test-restore comparing against the source.
- [ ] **Is there an off-site / independent copy of irreplaceable data?** · Applies when: the diff introduces data that cannot be regenerated from a source already stored elsewhere. · Block if: the only copy (or the only backup) shares the failure domain of the data (same disk, host, account).
- [ ] **Do backup frequency and restore speed meet stated RPO/RTO?** · Applies when: the diff sets a backup schedule or mechanism for important data. · Block if: the interval loses more than the acceptable data, or restoring it would exceed the outage budget.
- [ ] **Is effort matched to what actually needs backing up?** · Applies when: the diff adds backup machinery. · Block if: it backs up data already durable elsewhere or trivially regenerable (over-engineering), or omits the one irreplaceable thing because the system is small (under-engineering).

## In the factory
- **The work product is backed up; the operational state is not.** The code, cards, PRs and branch history live on GitHub — an off-machine, versioned copy, so the thing the factory produces is safe (a `git clone` restores it). That is the right instinct and covers the valuable, irreplaceable output.
- **But the local-only state has zero backups.** `.env` (the Claude OAuth token, HMAC webhook secrets, the CF Access service token), the tunnel credentials (`~/.cloudflared/<id>.json` and `cert.pem`), and the run/rejection history (`logs/`, `state/`, `.factory-logs/rejected.jsonl`) are all gitignored (`.gitignore`) and exist only on this Mac's disk. A disk loss means regenerating secrets and tunnel credentials by hand and losing the run history. Nothing is strictly irreplaceable (the secrets are reissuable, the history is low value), but there is no documented backup set and recovery is manual — the backups half of disaster recovery (083). Added to GAPS.md (low).
- **Correctly not backed up:** the OpenHands image (re-pullable by digest — 007-docker.md), the uv caches, the sandbox workdirs (ephemeral). Backing these up would be the over-engineering the card warns about.
- Not applicable at today's load: scheduled snapshots, off-site backup storage, retention tiers, automated restore drills. The right-sized fix is a short documented copy of `.env` + tunnel creds to one off-machine location, which 083-disaster-recovery.md frames.

## Proof
`python3 knowledge/systems/proofs/084_backups.py`, a real tar backup of a small data dir, corrupted mid-archive (a bad-sector/bit-rot overwrite), then checked two ways:
```
A  "backup exists" check (file present, non-empty): OK  -> false confidence, the archive is corrupt
A  test-restore check (extract + compare checksums): RESTORE FAILED  -> the only check that catches it
```
The archive is present and non-empty, so a "did the backup run?" check passes — false confidence. Only extracting it to a scratch dir and comparing checksums against the source reveals that it will not restore. A backup is not done until a restore has been verified.

## Related
083-disaster-recovery.md, 085-failover.md, 032-replication.md, 081-database-migrations.md, 067-secrets-management.md, 072-encryption-at-rest.md, 104-infrastructure-as-code.md

## Sources
- "Backup and recovery" / 3-2-1 and tested restores, AWS Prescriptive Guidance & Well-Architected (Reliability): https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/back-up-data.html
- "Disaster recovery / RPO and RTO", AWS: https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html
