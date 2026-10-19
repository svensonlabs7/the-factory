# 106. Helm Charts

Track: K. Infrastructure · Status: proven · Updated: 2026-10-19

## What it is
Helm is the package manager for Kubernetes (008-kubernetes.md). A **chart** bundles a set of templated manifests plus a `values.yaml` of defaults; you install it with your own value overrides, and Helm renders the templates into concrete manifests and applies them as a tracked **release**. Because a release is versioned, `helm upgrade` moves it forward and `helm rollback` returns it to a previous revision (055-rollbacks.md). Charts are the unit of reuse and distribution for k8s apps: parameterise once (image tag, replica count, resource limits, hostnames) and deploy the same chart to many environments with different values. The templates produce YAML by **string substitution** (Go templates), and since YAML is whitespace-significant, the characteristic Helm hazard is a templating bug — usually indentation — that renders structurally wrong or invalid YAML (proof). `helm template` and `helm lint` render and parse locally, catching that before `helm install` touches a cluster.

## When it is worth it
- Worth it when you already run Kubernetes and deploy the same app across environments or repeatedly: a chart turns a pile of manifests into one parameterised, versioned, rollback-able unit, and public charts let you install complex software (a database, ingress controller) without writing manifests by hand.
- It presupposes Kubernetes. If k8s itself is over-engineering for the workload (008: a single host or few containers), Helm is over-engineering on top of over-engineering — a templating-and-release layer for manifests you have no cluster to run. Even within k8s, a single static manifest applied once does not need a chart; templating earns its keep only when values actually vary or the release is upgraded over time.

## How it fails
- **Indentation/templating bug renders wrong YAML:** a value injected at the wrong indentation produces a manifest that parses to the wrong structure (a block lands under the wrong key, or a map becomes empty) or fails to parse — shipped only because nobody rendered and validated it first (proof).
- **Applying without `helm template`/`lint`/`--dry-run`:** the broken render reaches the cluster, where k8s may reject it or, worse, accept a semantically wrong object.
- **Values drift and precedence confusion:** the same chart installed with different ad-hoc `--set` flags in different places, so no file captures what is actually deployed (104-infrastructure-as-code.md: drift).
- **Secrets in values:** credentials put in `values.yaml` or `--set` land in the release and in cluster state in plaintext (067-secrets-management.md).
- **Non-idempotent or destructive upgrade:** a chart change forces replacement of a stateful resource (a PVC/StatefulSet) and an unreviewed `upgrade` destroys data (105-terraform.md: unreviewed plan).
- **Unpinned chart/subchart versions:** `helm upgrade` pulls a newer chart or dependency that changes behaviour (108-dependency-hell.md).

## Review checklist
- [ ] **Is the rendered output validated before install/upgrade?** · Applies when: the diff adds or changes a Helm chart or its values. · Block if: there is no `helm template`/`lint`/`--dry-run` step, so an indentation or templating bug can render wrong YAML that only fails (or silently misbehaves) at apply.
- [ ] **Is the deployed configuration captured in a values file, not ad-hoc flags?** · Applies when: the diff deploys or upgrades a release. · Block if: the real configuration lives in scattered `--set` flags with no committed values file, so what is deployed is not reproducible.
- [ ] **Are chart and subchart versions pinned?** · Applies when: the diff adds a chart dependency or an upgrade. · Block if: versions float, so a later `upgrade` changes behaviour unexpectedly.
- [ ] **Is a chart justified over a plain manifest, and k8s over nothing?** · Applies when: the diff introduces Helm. · Block if: there is no Kubernetes cluster for it, or a single static manifest with no varying values would do — templating and releases without variation or upgrades are overhead.

## In the factory
- **No Helm, because there is no Kubernetes** (008-kubernetes.md). A chart here would be a templating and release layer over manifests the factory has no cluster to apply. Clear over-engineering.
- **The factory does template a config, but in text, not whitespace-significant YAML, so this card's footgun does not bite.** `webhook_adapter.py:88` renders `HEARTBEAT.md` from `HEARTBEAT.template.md`, and `:251-280` builds the agent prompt from `TASK_PROMPT_TEMPLATE.format(...)`. These produce Markdown/plain text where indentation is cosmetic, and `str.format` does not re-interpret substituted values (a brace in `user_task` is inserted literally, not re-expanded), so there is no injection or structural-corruption risk. No gap.
- **The release/rollback idea the factory does need it has elsewhere:** versioned, revertible deployment is git + the branch/PR flow and `055-rollbacks.md`, not Helm releases.
- Not applicable at today's load: charts, `values.yaml`, `helm template/lint/upgrade/rollback`, chart repositories, subcharts.

## Proof
`uv run --with pyyaml python 106_helm.py`, a Helm-style template injecting a labels map at different indentation, then rendering-and-parsing as `helm template`/`lint` would:
```
A  render the labels block at different indentation, then render-and-validate (what `helm template` does):
   indent=4 (correct): parsed metadata.labels = {'app': 'factory', 'tier': 'web'}  -> correct
   indent=2 (bug)    : parsed metadata.labels = None  -> WRONG STRUCTURE
B  what each workflow would do with the indent=2 chart:
   helm template/lint: renders locally, parse shows labels wrong=True -> caught before install
   blind kubectl apply of the rendered text: ships the mis-structured Deployment to the cluster
```
At the correct indentation the labels parse under `metadata.labels`; two spaces short, they detach and `metadata.labels` parses as empty — a manifest that is valid YAML but the wrong object. Rendering and parsing locally (what `helm template`/`lint` do) catches it; a blind apply ships it. The lesson: template-generated YAML must be rendered and validated before it is applied.

## Related
008-kubernetes.md, 104-infrastructure-as-code.md, 105-terraform.md, 055-rollbacks.md, 067-secrets-management.md, 108-dependency-hell.md

## Sources
- "Charts" and "The Chart Template Developer's Guide", Helm documentation: https://helm.sh/docs/topics/charts/
- "Helm Commands: template, lint, upgrade, rollback", Helm documentation: https://helm.sh/docs/helm/helm_template/
