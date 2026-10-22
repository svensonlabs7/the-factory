# 6. CI/CD

Track: E. Delivery and change · Status: proven · Updated: 2026-10-18

## What it is
Continuous integration (CI) means everyone merges small changes into one mainline often, at least daily, and every merge is checked by an automated, self-testing build. A red build is fixed first, usually by reverting. Continuous delivery (CD) keeps the mainline releasable at all times, with a scripted deploy to any environment. Continuous deployment goes one step further and ships every green change automatically.

A green result means something only if two things hold:
- It tested what will actually land: the change merged with the current mainline, not with the base the branch started from.
- It tested in a clone of production: same language version, same dependency versions, same configuration.

When either is false, CI can be green while main or production is broken.

## When it is worth it
CI is worth it for any shared codebase. A self-testing build on every PR, required before merge, is the minimum. A fast build (Fowler's target is ten minutes) keeps merges small. Pin the build so CI and production run the same versions. Merge queues, multi-stage pipelines, canary deploys and automated rollback pay off when many changes land per day, or when a bad deploy reaches many users. For one host, one operator and a few PRs a day, a required PR build plus a scripted, verified deploy is enough.

## How it fails
- **Semantic conflict on a stale green:** two PRs each pass against an old base and merge with no textual conflict. Main is now broken, and no check ever ran on that combination.
- **CI is not a clone of production:** CI installs whatever versions are newest that day, on a different Python. Production runs other versions → green CI proves nothing about the code that serves traffic.
- **Unpinned build:** the same commit builds differently on different days → a dependency release breaks CI or production with no code change, and nobody can reproduce the last good build.
- **Merged but not deployed:** CD stops at the merge, and someone must remember to restart → production silently runs old code.
- **Slow or flaky build:** people batch changes, rerun until green, or bypass the gate.
- **Gate editable by the PR:** a PR changes the workflow or the skill that reviews it → it approves itself.

## Review checklist
- [ ] **Is the change tested on top of the current mainline?** · Applies when: the diff changes branch protection, merge settings or how PRs are merged. · Block if: it turns off "require branches to be up to date" (or a merge queue) and puts nothing in its place.
- [ ] **Does CI run the versions production runs?** · Applies when: the diff adds or changes a dependency, a runtime version, or the command that installs either in CI or in the deploy. · Block if: the dependency or version it adds or changes is unpinned, or is pinned in CI but not in production (or the reverse).
- [ ] **Is every new check required, and does it fail closed?** · Applies when: the diff adds a CI job or lane. · Block if: the job is not a required check, or a skipped, crashed or timed-out run can count as passing.
- [ ] **Can the PR change the gate that reviews it?** · Applies when: the diff touches workflows, review skills or the scripts they call. · Block if: the reviewing job runs the PR's own copy of them with access to secrets.
- [ ] **Does the deploy reach the running process?** · Applies when: the diff changes how a long-running service is started or deployed (its launch config, entrypoint, dependencies or runtime). · Block if: the PR does not say how the change is applied to the running service and how to check it took effect.

## In the factory
- Branch protection on `main` requires all six checks (`thermo-nuclear`, `ponytail-review`, `ux-laws`, `tests`, `lint`, `secrets`) with `strict: true` and `enforce_admins: true` (`gh api …/branches/main/protection`). Every merge is tested on top of the current main, and admins cannot skip it. That closes the semantic-conflict case in the proof. Right.
- `.github/workflows/qa-gate.yml:3-5,38-44`: `pull_request_target` checks out the base commit and reads the PR only as git refs, so a PR cannot edit its own reviewers. `:31-36` fails fork PRs instead of skipping them, because a skipped job would satisfy the required check. Right.
- `factory/intake/webhook_adapter.py:352-370` (`_gate_results`): the adapter waits until the PR is at the head it pushed, then reads the required checks for that head. It never acts on the previous commit's results. Right.
- Gap (medium): nothing is pinned, and CI is not a clone of production.
  - `.github/workflows/tests.yml:15` installs unpinned `pytest fastapi httpx pyyaml` on the runner's Python 3.12.
  - The adapter runs from `factory/intake/com.svenson.factory-intake.plist:9-16` (`uv run --with fastapi --with uvicorn --with python-dotenv`), also unpinned, on Python 3.11.15.
  - Measured today: the live adapter has FastAPI 0.144.0, the last `tests` run installed 0.145.0, and a fresh resolve gets 0.146.0. That is three versions, and production runs none of the ones CI tested (see GAPS.md).
- The deploy is manual: merge, then restart the adapter. GAPS.md already has the stale-code row under Health Checks (`/health` does not report the running commit).
- `timeout-minutes` is missing on every job: see the Timeouts row in GAPS.md.
- Not applicable at today's load: a merge queue, `concurrency` cancellation, canary deploys and automated rollback. The adapter waits for every check before it pushes again, so no superseded review runs, and PRs arrive a few a day, so strict mode's rebase cost is small.

## Proof
`python3 -I knowledge/systems/proofs/006_cicd.py`. A runs real git in scratch repos. B resolves with `uv pip compile --exclude-newer <date>`.
```
A  CI on each branch against the old base: a green, b green
A  main after merging a: green
A  not strict: merge b on its stale green -> textual conflict: False; main is now red (AttributeError: module 'lib' has no attribute 'fetch')
A  strict: b updated with main and re-tested -> red (AttributeError: module 'lib' has no attribute 'fetch'), merge blocked; main stays green
B  requirement 'fastapi' installed on
     2025-01-01: fastapi 0.115.6 starlette 0.41.3
     2025-09-01: fastapi 0.116.1 starlette 0.47.3
     2026-10-18: fastapi 0.146.0 starlette 1.9.0
B  requirement 'fastapi==0.110.0' installed on
     2025-01-01: fastapi 0.110.0 starlette 0.36.3
     2025-09-01: fastapi 0.110.0 starlette 0.36.3
     2026-10-18: fastapi 0.110.0 starlette 0.36.3
```
Live versions: the adapter's interpreter (PID 40944) reports `3.11.15 fastapi 0.144.0 starlette 1.8.0`. The latest `tests` run log shows `python3.12/site-packages` and `fastapi-0.145.0`.

## Related
055-rollbacks.md, 051-feature-flags.md, 053-canary-releases.md, 104-infrastructure-as-code.md, 011-timeouts.md, 056-health-checks.md, 103-semantic-versioning.md, 107-build-caching.md, 108-dependency-hell.md

## Sources
- "Continuous Integration", Martin Fowler: https://martinfowler.com/articles/continuousIntegration.html
- "Control the concurrency of workflows and jobs", GitHub Actions documentation: https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs
