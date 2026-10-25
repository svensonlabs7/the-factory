# 105. Terraform

Track: K. Infrastructure · Status: proven · Updated: 2026-10-19

Triggers: files `\.tf(vars)?$|\.terraform\.lock\.hcl$` · lines `(?i)\bterraform\b|\bopentofu\b` · tripwire

## What it is
Terraform is the most common declarative IaC tool (104-infrastructure-as-code.md). You describe desired resources in HCL config; Terraform keeps a **state file** recording what it has created and each resource's real attributes; and it works in two steps: `plan` diffs config against state (and the live provider) to show exactly what it will add, change or destroy, and `apply` makes those changes and updates state. **Providers** translate Terraform's resources into API calls for AWS, Cloudflare, GitHub, Kubernetes and so on. The state file is the heart of the model and its biggest hazard: it is the record of reality, often holds resource attributes (and sometimes secrets) in plaintext, and must be shared carefully. Because two applies editing one state concurrently race on read-modify-write, Terraform **locks** the state for the duration of an apply (via the backend — S3+DynamoDB, Terraform Cloud, etc.), and stores it in a shared **remote backend** so a team sees the same state.

## When it is worth it
- Worth it when infrastructure spans real cloud providers, must be reproduced across environments, or is changed by a team: Terraform gives a reviewable `plan`, a durable record of what exists, and provider coverage so the whole stack (DNS, compute, IAM, networking) is one codebase. It shines for multi-resource, multi-environment, multi-person infra.
- Over-engineering for a single host with a handful of local services and no cloud provider API to drive: the state file, remote backend, locking and provider setup are overhead with nothing to manage. Committed config files plus an idempotent install script (the factory's right-sized answer) deliver the IaC discipline without the machinery. Introduce Terraform when there is actual cloud infrastructure whose lifecycle it would own.

## How it fails
- **Unlocked concurrent apply:** two applies against one state race and lose an update or corrupt the state (proof). The fix is a locking backend.
- **Lost or corrupted state:** the state file is deleted, diverges from reality, or is edited by hand; Terraform then plans against a wrong picture and can orphan or destroy live resources. State is backed up and never hand-edited (except via `terraform state` commands).
- **Secrets in state:** resource attributes (passwords, keys) land in the state file in plaintext; an unencrypted or shared backend leaks them (067-secrets-management.md).
- **Applying without reading the plan:** a seemingly small config change forces a destroy-and-recreate of a stateful resource (a database), and an unreviewed `apply` executes it — data loss (104: no plan/review before apply).
- **Drift from out-of-band change:** someone edits a resource in the console; the next plan wants to revert it, surprising everyone (104: drift).
- **Provider/version drift:** unpinned provider or module versions change behaviour between runs (108-dependency-hell.md).

## Review checklist
- [ ] **Is the state backend locked and shared?** · Applies when: the diff configures Terraform state or adds applies that can run concurrently (CI, more than one operator). · Block if: state is local or on a backend without locking, so two applies can race and corrupt it.
- [ ] **Was the `plan` reviewed before `apply`, especially for replacements?** · Applies when: the diff changes a resource that could force replacement of a stateful resource. · Block if: apply runs with no reviewed plan showing the add/change/**destroy** counts.
- [ ] **Are provider and module versions pinned?** · Applies when: the diff adds or upgrades providers/modules. · Block if: versions float, so a later run silently changes behaviour.
- [ ] **Is Terraform the proportionate tool here?** · Applies when: the diff introduces Terraform. · Block if: there is no cloud/provider infrastructure for it to manage and committed config plus an install script would do — but do not accept dashboard-clicking as the alternative.

## In the factory
- **No Terraform, and that is the right call.** The factory has no cloud infrastructure for a provider to drive: one Mac, one Colima VM, one `cloudflared` tunnel, two launchd services, a Docker network. Its IaC is committed config files applied by a runbook (104-infrastructure-as-code.md). Standing up Terraform with a remote state backend and the Cloudflare provider to manage one tunnel would be overhead with almost nothing to manage.
- **If it ever did adopt Terraform**, the natural first target is the Cloudflare side — the tunnel, the two DNS records (097-dns.md) and the Access policies — which today are created by `cloudflared` CLI calls and dashboard clicks and are the least codified part of the system (the IaC gap in GAPS.md). That would turn those manual steps into a reviewable `plan`. It is a worthwhile future step, not a gap to open now, and no new gap is added here.
- **The locking lesson already lives in the factory** without Terraform: the adapter serialises runs through a single-worker executor and an event-loop capacity check with no `await` before the write (`webhook_adapter.py:151,227-231`), the same "serialize the mutation so two actors cannot race the shared state" idea this card proves (039-race-conditions.md, 043-thread-safety.md).
- Not applicable at today's load: HCL, state backends, providers, workspaces, `plan`/`apply` pipelines.

## Proof
`python3 knowledge/systems/proofs/105_terraform.py`, two concurrent "applies" adding distinct resources to one shared state, with a barrier forcing the racy interleaving:
```
no lock       : final state has ['tunnel']  -> an apply was LOST
with state lock: final state has ['egress', 'tunnel']  -> both kept
```
Without a lock both applies read the empty state, each writes back its own single resource, and the last writer wins — the other resource is silently lost from state, so Terraform no longer knows it exists. With a state lock the applies serialise and both resources are recorded. Identical across three runs. This is why Terraform locks state for the duration of an apply.

## Related
104-infrastructure-as-code.md, 007-docker.md, 039-race-conditions.md, 043-thread-safety.md, 067-secrets-management.md, 108-dependency-hell.md, 083-disaster-recovery.md

## Sources
- "State" and "State Locking", Terraform documentation: https://developer.hashicorp.com/terraform/language/state/locking
- "Terraform workflow: plan and apply", HashiCorp: https://developer.hashicorp.com/terraform/intro/core-workflow
