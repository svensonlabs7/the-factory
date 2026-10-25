# 88. Cost Optimization

Track: I. Performance and scaling · Status: proven · Updated: 2026-10-19

Triggers: files `^\.github/workflows/qa-gate\.yml$|^factory/qa/` · lines `claude -p|--model\b|MAX_RETRIES|AGENT_TIMEOUT|MAX_RUNS_PER_DAY|(?i:\b(opus|sonnet|haiku)\b)`

## What it is
Cost optimization is delivering the same output for less: less money, or less of whatever resource is scarce. The AWS Well-Architected cost pillar's design principles name the method:
- **Measure overall efficiency:** "measure the business output of the workload and the costs associated with delivery".
- **Analyze and attribute expenditure:** know which workload and which step spends what.
- **Adopt a consumption model:** pay only for what is used; stop what is idle.
- **Stop spending on undifferentiated heavy lifting:** use managed services where they are cheaper than running your own.

The unit that matters is cost per unit of output (per request, per order, per merged PR), not total spend. The first step is always attribution. Without it, optimization guesses at the wrong line item.

## When it is worth it
Cost work is worth it once spend, or consumption of a capped resource, is significant and measurable: a cloud bill that grows with traffic, a quota that throttles work, idle capacity. The biggest wins are usually structural: not doing work that produces nothing (skipping unneeded steps, failing fast before expensive stages), right-sizing, and turning off idle resources. Micro-tuning a line item that is a few percent of the total, or adding cost tooling before there is a meaningful bill, is over-engineering.

## How it fails
- **No attribution:** total spend is known, but not which workload or step drives it → the wrong thing gets cut.
- **Paying for work that produces nothing:** expensive steps run on inputs that cannot benefit (a UI review on a PR with no UI files, a full pipeline on a change that will be abandoned).
- **Idle capacity:** environments, warm instances or reservations billed while unused (089-cold-starts.md).
- **Cutting reliability to cut cost:** removing redundancy, retries or reviews that prevented incidents more expensive than they cost.
- **Optimizing the cheap resource:** saving compute minutes that are free while the scarce resource (a quota, a licence, people's time) is spent freely.
- **Unbounded consumption:** no cap on per-run or per-day spend, so a loop or retry storm becomes a large bill (001-rate-limiting.md).

## Review checklist
- [ ] **Is the change's cost on the binding resource known?** · Applies when: the diff adds a step that consumes a metered or capped resource (paid API calls, LLM sessions, CI minutes on a paid plan, cloud resources). · Block if: the added consumption per unit of output is not stated or measured.
- [ ] **Does expensive work skip inputs that cannot benefit?** · Applies when: the diff adds an expensive step to a pipeline that runs on every change or request. · Block if: it runs unconditionally where a cheap check (paths changed, input type) could skip it without losing coverage.
- [ ] **Is consumption capped?** · Applies when: the diff adds a loop, retry or automation that consumes a metered resource. · Block if: there is no per-run or per-day limit, so a failure mode can consume without bound.
- [ ] **Is idle capacity turned off or justified?** · Applies when: the diff provisions always-on resources. · Block if: they sit idle most of the time with no measured need for warm capacity.
- [ ] **Is the saving worth its risk?** · Applies when: the diff removes a review, retry, redundancy or check to save cost. · Block if: no comparison shows the saving exceeds the expected cost of what the removed safeguard prevents.

## In the factory
- The binding cost is the Claude plan's usage, a capped subscription, not money per call. GitHub Actions minutes cost nothing: "GitHub Actions usage is free… for public repositories that use standard GitHub-hosted runners", and this repo is public.
- Attribution from the real record:
  - 87 gate runs for 57 PRs (41 merged, 16 closed);
  - about 2.07 Claude review sessions per gate run, so about 180 sessions in all, or 4.4 per merged PR, plus the builder's sessions on factory-built PRs (proof).
- Skipping work that cannot benefit already pays. The `ux-laws` lane's path scoping (`.github/workflows/qa-gate.yml:24-28`, `factory/qa/scope.sh`) ran its Claude review on 2 of the last 30 gate runs, avoiding 28 of 90 possible review sessions (31%). Right.
- Consumption is capped: 30 runs a day, 5 in flight, 2 fix rounds per run (`factory/intake/webhook_adapter.py:58,72-73`). Right.
- Spend with no merge: 16 of 87 gate runs (18%), about 33 review sessions, were on PRs later closed. Many of those PRs were deliberate experiments.
- Exact attribution is impossible. Token usage per run is not observable (every run log reports `total 0`), already the Observability row in GAPS.md.
- The two code-review lanes also review docs-only PRs (5 of 57 PRs touched only Markdown). A paths filter like `ux-laws`' could skip them. That is a choice, not a defect: prose reviews can still catch problems.
- Not applicable at today's load: FinOps tooling, reservations and cost dashboards.

## Proof
`python3 -I knowledge/systems/proofs/088_cost.py`, read-only `gh` calls against the repo's real PRs and gate runs:
```
A  87 gate runs for 57 PRs (1.53 runs per PR); 41 merged, 16 closed
A  Claude review sessions per gate run 2.07 -> about 180 sessions, 4.4 per merged PR
B  last 30 gate runs: Claude review ran thermo-nuclear 30, ponytail-review 30, ux-laws 2 of 30
B  ux-laws path scoping avoided 28 of 90 possible review sessions (31%)
C  gate runs on PRs that were then closed: 16 of 87 (18%), about 33 review sessions with no merge
```
The per-run rate is taken from the last 30 runs and extrapolated to all 87.

## Related
001-rate-limiting.md, 061-metrics.md, 066-observability.md, 092-throughput.md, 094-tail-latency.md, 089-cold-starts.md, 107-build-caching.md

## Sources
- "Design principles", AWS Well-Architected Framework, Cost Optimization Pillar: https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/design-principles.html
- "GitHub Actions billing", GitHub Docs: https://docs.github.com/en/billing/concepts/product-billing/github-actions
