# 103. Semantic Versioning

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

Triggers: lines `==\d|>=\d|~=\d|@v\d|--with \w|requires-python|(?i:returncode|in (result\.)?(stdout|stderr))`

## What it is
Semantic Versioning (SemVer) gives a version number, `MAJOR.MINOR.PATCH`, a promise about compatibility:
- **MAJOR** goes up for incompatible API changes.
- **MINOR** goes up for backward-compatible features.
- **PATCH** goes up for backward-compatible fixes.

The promise covers only a declared public API. A released version must never change. Major version zero is special: "Anything MAY change at any time." So a `0.y` minor bump can break you.

Consumers turn the promise into ranges (`^1.4`, `~=1.4`, `<2`) and lock files. Hyrum's Law marks the limit: with enough users, every observable behaviour is depended on, whatever the contract says. Error message wording, output order and timing are not covered by any version number, so code that parses them can break on a patch release.

## When it is worth it
Publishing SemVer is worth it for anything others depend on: libraries, CLIs, APIs. Consuming it well matters everywhere:
- a range is acceptable only where the publisher keeps the promise and the version is at least 1.0;
- exact pins plus a lock file are needed for anything that must build the same tomorrow;
- tools whose behaviour you parse (CI actions, CLIs, container images) are pinned exactly, or by digest.

Running your own release numbering (changelogs, version bumps, tags) for an application nobody else imports is over-engineering. A commit SHA is its version.

## How it fails
- **Trusting `0.x` ranges:** `fastapi>=0.100` or no pin at all → a minor release that may break is installed silently.
- **Major bump picked up unpinned:** a dependency's 1.0 removes a deprecated API → code using it fails on the next fresh install.
- **Hyrum's Law:** code matches a tool's human-readable output or error text → a patch release rewords it, and the code takes the wrong branch, with no version signal.
- **Mutable tags:** `@v4` or `:latest` is moved by its publisher (or an attacker) → different code runs under the same name.
- **Accidental break in a minor or patch:** the publisher breaks SemVer → only a lock file, or a test that runs on update, protects you.
- **Pins never updated:** exact pins without an update routine → known-vulnerable versions stay for good.

## Review checklist
- [ ] **Is every new dependency pinned in a way that matches its stability?** · Applies when: the diff adds or changes a dependency, a tool version, an action or an image. · Block if: a `0.x` package or a tool whose output the code parses is given a range or no pin, or an image or action that receives secrets is referenced by a mutable tag from an untrusted publisher.
- [ ] **Does the code depend on unversioned behaviour?** · Applies when: the diff branches on a tool's or library's message text, output formatting or ordering. · Block if: a structured interface (JSON output, an exit code, an API) gives the same signal and is not used.
- [ ] **Is a major-version bump handled deliberately?** · Applies when: the diff raises a dependency's major version, or its `0.x` minor. · Block if: the changelog's breaking changes were not checked against the code's uses, or no test covers the code paths that use it.
- [ ] **Is the version promise of what we publish kept?** · Applies when: the diff changes a library, CLI or API that others consume with a version. · Block if: a breaking change ships without a major bump (or a new API version, see 102-api-versioning.md).
- [ ] **Is version ceremony justified?** · Applies when: the diff adds release numbering, changelog tooling or version-bump automation. · Block if: nothing outside the repo depends on the version number.

## In the factory
- Exact pins where the factory parses or trusts a tool. Right:
  - `.github/workflows/qa-gate.yml:42` (`@anthropic-ai/claude-code@2.1.296`);
  - `.github/workflows/static.yml:16,26-29` (`ruff==0.17.0`, `mypy==2.4.0`, and `gitleaks` 8.30.1 checksum-pinned);
  - `factory/build/run_agent.py:3,23-24` (`openhands-sdk==1.54.0`, `openhands-workspace==1.54.0`, and the agent-server image pinned by digest, with a comment tying the image to the SDK version).
- `actions/checkout@v4` and `actions/upload-artifact@v4` are tags from GitHub itself. 067-secrets-management.md accepts that, and this card agrees.
- FastAPI is `0.x`, so SemVer promises nothing between its minors. It is unpinned in CI and in the adapter's launch (the CI/CD row in GAPS.md).
- `factory/intake/webhook_adapter.py:173` uses `lifespan=`, so the adapter already survives Starlette 1.0's removal of `on_startup`/`on_event` (proof A). Right.
- Gap (low), Hyrum's Law: the adapter depends on message text no version promises.
  - `_gate_results` (`:364`) keeps waiting only when `gh pr checks` fails with text containing "checks reported". gh 2.101.0's wording is "no required checks reported on the '%s' branch". A reworded message makes the wait fail on its first poll, so every run errors after a successful build (proof B).
  - gh is Homebrew-managed and unpinned (2.101.0 installed, 2.102.0 already available), so the next `brew upgrade` can change it.
  - `USAGE_LIMIT_RE` and `RESET_TIME_RE` (`:456-457`) parse Claude Code's usage-limit message the same way.
  - `gh pr view --json statusCheckRollup` gives the same signal as structured data (see GAPS.md).
- Not applicable at today's load: publishing versions of the factory itself. It is an application; the commit SHA is its version.

## Proof
A, the real packages: `uv run --with starlette==<v> python -c "Starlette(on_startup=[...])"`:
```
starlette 0.47.3: Starlette(on_startup=...) -> accepted; on_event exists: True
starlette 1.9.0: Starlette(on_startup=...) -> TypeError: Starlette.__init__() got an unexpected keyword argument 'on_startup'; on_event exists: False
```
B: `pytest -s knowledge/systems/proofs/103_semver.py`. This is the real `_gate_results`, through `tests/test_adapter.py`'s fixture, with `_run` playing gh: two "no checks yet" polls, then results:
```
B  gh 2.101.0 wording: waited, then {'tests': 'pass'}
B  reworded by a gh release: RuntimeError after 1 poll(s): gh pr checks: no required status checks found for 'factory/x'
```
The installed gh contains both of its wordings: `strings $(which gh)` shows "no checks reported on the '%s' branch" and "no required checks reported on the '%s' branch".

## Related
102-api-versioning.md, 082-schema-versioning.md, 006-ci-cd.md, 067-secrets-management.md, 012-retries.md, 029-read-replicas.md

## Sources
- "Semantic Versioning 2.0.0": https://semver.org/
- "Hyrum's Law", Hyrum Wright: https://www.hyrumslaw.com/
