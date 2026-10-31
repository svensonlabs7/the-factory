# 83. Disaster Recovery

Track: L. Operations · Status: proven · Updated: 2026-10-19

Triggers: files `^infra/|\.plist$|(^|/)\.gitignore$` · lines `(?i)\.env\b|credentials-file|cert\.pem|launchagents|brew install`

## What it is
Disaster recovery (DR) is restoring service after the whole environment is lost — a dead disk, a destroyed host, a region outage, a ransomware event — as opposed to a single component failing (85-failover.md). It is defined by two targets: **RPO** (recovery point objective — how much recent data you may lose, set by backup frequency — 084-backups.md) and **RTO** (recovery time objective — how long recovery may take). AWS's DR whitepaper lays out four strategies that trade cost against those targets:
- **Backup & restore** — rebuild from backups on demand; cheapest, RTO of hours;
- **Pilot light** — core data replicated and minimal services idle, scaled up on disaster;
- **Warm standby** — a scaled-down copy always running, scaled up on failover; RTO of minutes;
- **Multi-site active/active** — full copies serving in parallel; near-zero RPO/RTO, most expensive.
The rule that bites is that an **untested DR plan has an unknown RTO**: any step whose input is neither backed up nor written in a runbook must be improvised during the outage, and you only learn how long that takes when it happens (proof). DR is proven by drills, not by intention.

## When it is worth it
- Every system that matters needs *a* DR answer, but the *strategy* must match the stakes. Backup & restore is right for systems that can tolerate hours of downtime; warm standby or active/active is for those where minutes of downtime or any data loss is unacceptable. Picking a tier above the business need is wasted spend (a hot multi-region standby for a service nobody would miss for a day); picking below it is a gamble that surfaces as an unrecoverable outage.
- At small scale the valuable, cheap core is not infrastructure — it is a *written, tested rebuild runbook* and an off-machine copy of everything the rebuild needs. Standing up warm standby for a single-operator tool is over-engineering; having no idea how to rebuild it, or finding mid-outage that a required secret was never backed up, is the under-engineering.

## How it fails
- **Untested plan, unknown RTO:** a step needs an input (a secret, a key, a credential) that was never backed up or documented, so recovery stalls on improvisation (proof: the factory's rebuild is runbooked except for the un-backed-up secrets).
- **RPO/RTO unmet by the chosen strategy:** backups are too old (RPO miss) or restoring the volume takes far longer than the outage budget (RTO miss).
- **Backups present but unrestorable:** the DR copy cannot actually be restored (084-backups.md).
- **Dependencies forgotten:** the data is recovered but a credential, DNS record, certificate or external integration needed to bring the service up is not (097-dns.md, 071-tls.md).
- **DR environment drifts:** a standby that was never kept in sync with production fails over into a stale or incompatible state (104-infrastructure-as-code.md).
- **Plan exists only in one person's head:** the one who knows how to recover is unavailable during the disaster.

## Review checklist
- [ ] **Is every input the rebuild needs recoverable from somewhere off the lost machine?** · Applies when: the diff adds a component whose loss would require a rebuild (a service holding local secrets, state, or config). · Block if: a required secret, key, credential or state exists only on the machine that the disaster destroys, with no off-machine copy.
- [ ] **Is the recovery procedure written down and runnable by someone else?** · Applies when: the diff changes how the system is provisioned or what it depends on. · Block if: the rebuild steps live only in memory or are out of date, so RTO depends on improvisation.
- [ ] **Does the DR strategy meet the stated RPO/RTO?** · Applies when: the diff sets or relies on a DR approach for important data/service. · Block if: backup frequency or restore speed cannot meet the data-loss and downtime targets the system actually requires.
- [ ] **Is the DR tier proportionate to the stakes?** · Applies when: the diff introduces DR infrastructure. · Block if: it builds warm standby / multi-site for a system that tolerates a slow rebuild (over-engineering), or leaves a business-critical system with only an untested backup (under-engineering).

## In the factory
- **The right strategy is backup & restore, and it is mostly in place.** The factory tolerates hours of downtime (one operator, no external SLA), so a rebuild-from-sources approach is correct; warm standby or multi-region would be over-engineering (86-multi-region-deployment.md). The code, cards and PRs are on GitHub, and the provisioning steps are written in the READMEs (`infra/cloudflare-tunnel/README.md`, `factory/intake/README.md`).
- **The hole is exactly what this card warns about: two rebuild steps are not recoverable from a backup.** Modelling the rebuild as a runbook, every step is estimable (~40 min) *except* restoring the `.env` secrets and the tunnel credentials, which are not backed up (084-backups.md) — so today's RTO is "40 min + unknown", improvised during the outage. The right-sized fix is the Backups gap's off-machine copy plus a DR note, after which the whole rebuild is runbooked at ~50 min.
- **The relevant gaps are already recorded; this card ties them together, so no new gap:** Backups (no off-machine secrets/creds), Infrastructure as Code (config applied by hand, can drift from the repo), and OAuth (no revoke/reissue runbook). DR is the story that connects them: a rebuild needs the off-machine copy *and* the runbook *and* the reissue steps.
- **Since #61 the rebuild is written down and its secrets are recoverable:** `infra/README.md` is the ordered rebuild with checks, and `infra/backup-secrets.sh` writes `.env` and the tunnel credentials to an AES-256 disk image (proven: a restore matched the source, and a wrong passphrase was refused). The operator still has to store a backup off this machine and time one drill; until then the RTO stays an estimate.
- **A DR drill has never been run** — the plan is untested, which by this card's rule means its true RTO is unverified. A single documented, timed rebuild on a scratch machine would convert the estimate into a fact.
- Not applicable at today's load: pilot light, warm standby, multi-site, cross-region replication, automated DR orchestration.

## Proof
`python3 knowledge/systems/proofs/083_disaster_recovery.py`, the factory's rebuild modelled as an ordered runbook where a step whose input is not backed up must be improvised:
```
today (secrets/creds NOT backed up)   : RTO = 40 min runbooked + UNKNOWN (improvised: ['restore .env secrets (OAuth, HMAC, CF Access)', 'restore / recreate tunnel credentials'])
after Backups fix (off-machine copy)  : RTO ~= 50 min, every step runbooked
```
Today the rebuild is fully runbooked (~40 min) until it reaches the two steps whose inputs live only on the lost disk; those must be improvised (reissue each secret at its provider, recreate the tunnel — which changes its id and forces a `config.yml` edit), so the real RTO is unknown. With the secrets and tunnel credentials copied off-machine, every step is runbooked and the RTO becomes a bounded ~50 min. An untested plan with a missing input has no knowable RTO.

## Related
084-backups.md, 085-failover.md, 086-multi-region-deployment.md, 032-replication.md, 104-infrastructure-as-code.md, 067-secrets-management.md, 055-rollbacks.md

## Sources
- "Disaster recovery options in the cloud" (the four strategies, RPO/RTO), AWS: https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html
- "Testing disaster recovery", Google SRE / AWS Well-Architected Reliability pillar: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/testing-disaster-recovery.html
