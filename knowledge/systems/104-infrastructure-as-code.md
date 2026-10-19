# 104. Infrastructure as Code

Track: K. Infrastructure · Status: proven · Updated: 2026-10-19

## What it is
Infrastructure as Code (IaC) means the servers, networks, DNS records, certificates and services that make up a system are defined in version-controlled files and created by a tool that makes reality match those files — instead of being clicked together in a console or set up by hand. The files are the source of truth: they are reviewed, diffed, and rolled back like any code. Two properties separate IaC from a setup shell script:
- **Idempotence:** applying the same definition twice is safe and a no-op the second time. You describe the *desired end state*, and the tool computes the difference from the current state and makes only the changes needed, rather than running create-steps that duplicate or error on a second run (proof A).
- **Drift reconciliation:** if reality drifts from the files (a manual edit, a failed change), the next apply detects the difference and corrects it (proof B).
Declarative tools (Terraform — 105, CloudFormation, Kubernetes manifests) do this by tracking state; configuration managers (Ansible, Chef) aim for idempotent steps. The payoff is a reproducible, auditable, reviewable environment.

## When it is worth it
- Worth it once infrastructure is more than trivial, is rebuilt or replicated (staging/prod, disaster recovery — 083), or is changed by more than one person: the files give review, history, and a repeatable build. It is the only sane way to recreate an environment after loss (083-disaster-recovery.md, 084-backups.md).
- The boundary is about *tooling weight*, not principle. Committing your config files and a scripted apply is right at almost any size. Standing up Terraform with remote state and providers for a single hobby host that will never be rebuilt from scratch is heavier than the payoff — but the underlying discipline (config in git, not clicked in a dashboard) still applies. The anti-pattern at every size is a "works on my machine" environment whose real definition lives only in a running host's memory.

## How it fails
- **Imperative, non-idempotent setup:** a create-script that is not safe to re-run duplicates resources or errors on the second run, so partial failures cannot be retried cleanly (proof A).
- **Config committed but applied by hand:** the files exist in git but must be manually copied into place, so the live copy silently drifts from the repo and editing the repo changes nothing until someone re-copies it (the factory's case — gap below).
- **Untracked drift:** someone fixes something directly in the console; the next apply either reverts the fix or, with no reconcile, the console and the files disagree forever.
- **State file mishandled:** the tool's state (what it thinks exists) is lost, shared without locking, or holds secrets in plaintext — corrupting it can orphan or destroy real resources (105-terraform.md).
- **Secrets in the code:** credentials committed alongside the infra definition (067-secrets-management.md).
- **No plan/review before apply:** applying without previewing the diff lets a one-line change destroy and recreate a stateful resource unseen.

## Review checklist
- [ ] **Is the setup idempotent and re-runnable?** · Applies when: the diff adds or changes a script/definition that provisions or configures infrastructure. · Block if: re-running it duplicates resources, errors on existing state, or otherwise is unsafe to apply twice.
- [ ] **Is the committed definition the thing that is actually applied?** · Applies when: the diff adds infra config to the repo. · Block if: the file must be manually copied to a live location with nothing verifying the live copy matches the repo, so drift is undetectable.
- [ ] **Is there a reviewable plan before a destructive apply?** · Applies when: the diff changes IaC for a stateful resource. · Block if: the change is applied with no previewed diff, so a destroy-and-recreate can happen unseen.
- [ ] **Is heavyweight IaC tooling proportionate here?** · Applies when: the diff introduces a full IaC tool (Terraform + remote state, etc.). · Block if: a single never-rebuilt host is involved and committed config plus a scripted apply would do — but do not accept "clicked in a dashboard" as the alternative.

## In the factory
- **Config is codified; provisioning is a manual runbook.** The real infra definitions live in git: `infra/cloudflare-tunnel/config.yml`, two launchd plists, `factory/build/egress.sh`, the digest-pinned image and `uv` script headers (`git ls-files`). That is genuine IaC discipline — reviewable, diffable, rolled back with the repo.
- **But standing it up is imperative and by hand.** `infra/cloudflare-tunnel/README.md:16-22` is a runbook: `cloudflared tunnel login/create`, `route dns`, `cp config.yml ~/.cloudflared/`, `cp …plist ~/Library/LaunchAgents/`, `launchctl load`; the intake has the same shape (`factory/intake/README.md:80`). The committed files must be hand-copied to their live locations, and nothing checks that the live `~/.cloudflared/config.yml` or the loaded plist still matches the repo. Editing the repo changes nothing until a human re-copies — the "committed but applied by hand" drift failure. Added to GAPS.md (low).
- **Right for one host:** full Terraform with providers and remote state for one Mac, one tunnel and two launchd services would be heavier than the payoff. The appropriate fix is small: a committed `install.sh` that copies the files idempotently and a check that the live copies match — not a new IaC platform.
- `egress.sh` is already idempotent the way IaC wants (it only recreates the proxy when its config hash changes, and reasserts the firewall rules every run), a good local example.
- Not applicable at today's load: Terraform/Ansible, remote state backends, multi-environment pipelines.

## Proof
`python3 104_iac.py`, a model of a declarative apply vs an imperative create:
```
A  imperative create, run twice:
    created tunnel (now 1 of it)
    created tunnel (now 2 of it) <- duplicate; not idempotent
A  declarative apply, run twice:
    run 1: +2 add, ~0 change  ['tunnel', 'egress']
    run 2: +0 add, ~0 change, 2 unchanged <- idempotent no-op
B  drift: an out-of-band edit changes the tunnel's port; next apply reconciles:
    apply: ~1 change ['tunnel'] -> tunnel back to {'port': 7654} (drift corrected)
```
The imperative create duplicates the resource on its second run; the declarative apply makes the changes once, is a no-op when reality already matches the desired state, and corrects an out-of-band drift on the next run. Idempotence and reconciliation are what make it IaC rather than a setup script.

## Related
105-terraform.md, 007-docker.md, 083-disaster-recovery.md, 084-backups.md, 067-secrets-management.md, 006-ci-cd.md, 055-rollbacks.md

## Sources
- "What is Infrastructure as Code?", HashiCorp: https://developer.hashicorp.com/terraform/intro
- "Infrastructure as code", AWS Well-Architected / Prescriptive Guidance: https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/introduction.html
