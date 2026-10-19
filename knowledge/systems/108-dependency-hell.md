# 108. Dependency Hell

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

## What it is
Dependency hell is what happens when the packages a program depends on, and the packages they depend on, stop fitting together or stop staying still:
- **Conflicts:** two dependencies need incompatible versions of a shared one (the "diamond"), so no install satisfies both. pip and uv report this as "no solution" (`ResolutionImpossible`).
- **Drift:** exact pins on the top-level packages still let the transitive tree move. Each fresh install pulls whatever the ranges allow that day, so the same pins build a different program next week.
- **Weight:** every dependency is code written by strangers that you now trust, together with all of its own dependencies (Russ Cox).

The defences:
- depend on less;
- isolate programs with incompatible needs into separate environments;
- lock the full resolved tree, with hashes, so every install is identical;
- upgrade on purpose: re-resolve, read what changed, run the tests.

## When it is worth it
Every program with third-party packages needs a lock of its full tree, as soon as it must run the same way tomorrow. Separate environments are worth it when two programs on one host need incompatible Python or package versions. Auditing each new dependency (maintenance, transitive weight, security history) is worth it in proportion to how much it pulls in and how much it is trusted with. Vendoring, private mirrors and in-house forks are for organisations with supply-chain requirements. For one host they are over-engineering, once a lock file exists.

## How it fails
- **Diamond conflict:** a new pin on a shared package (an old `pydantic`, `httpx` or `litellm`) cannot coexist with what another dependency requires → the install fails, or worse, a looser tool installs a broken combination.
- **Transitive drift:** top-level pins are exact, but a sub-dependency publishes a new major version → the next fresh environment breaks with no change in the repo.
- **One environment for everything:** two programs with different runtime needs share an interpreter → one of them cannot be installed or upgraded.
- **Small-package sprawl:** a dependency is added for a few lines of code → more trust, more updates, more exposure (left-pad).
- **Upgrade debt:** pins are never moved → a large, risky jump later, often forced by a security fix.
- **Unreviewed new transitive dependencies:** an upgrade silently adds packages nobody chose.

## Review checklist
- [ ] **Is the full dependency tree locked?** · Applies when: the diff adds or changes a dependency of a program that runs in production or CI. · Block if: only top-level versions are pinned, with no lock file, constraints file or `exclude-newer` cutoff that fixes the transitive tree.
- [ ] **Does a new dependency earn its weight?** · Applies when: the diff adds a third-party package. · Block if: the standard library or an existing dependency does the job in a few lines, or the package is unmaintained or pulls in a large transitive tree for a small use.
- [ ] **Are programs with incompatible needs isolated?** · Applies when: the diff merges two programs' requirements into one environment, or adds a package to a shared one. · Block if: their Python versions or shared packages conflict, or the merge forces either to downgrade.
- [ ] **Is the upgrade reviewed as a change?** · Applies when: the diff updates a lock file or raises pins. · Block if: it bumps a major version, or adds new transitive packages, without the tests passing and the notable changes named in the PR.
- [ ] **Is a mirror, vendoring or fork justified?** · Applies when: the diff vendors packages, adds a private index, or forks a dependency. · Block if: a lock file with hashes meets the need.

## In the factory
- `factory/build/run_agent.py:1-4`: the builder is a PEP 723 script with its own environment, on Python 3.12 and separate from the adapter. Right, and required:
  - `openhands-sdk==1.54.0` needs Python ≥3.12, while the adapter runs on 3.11.15;
  - the SDK's floors (`pydantic>=2.13.5`, `httpx>=0.28.1`, `litellm>=1.93.0`) rule out older pins (proof A).
- The two environments differ hugely in size: the adapter resolves to 15 packages (FastAPI, uvicorn, python-dotenv), the builder to 146. The adapter otherwise leans on the standard library and the `gh` and `git` CLIs. Right.
- Gap (medium): the builder pins its top level exactly but locks nothing below it.
  - Under the same two pins, 17 of 146 transitive packages changed between 2026-10-12 and 2026-10-19 (proof B). They include a major bump (`pillow` 12 → 13), three FastAPI `0.x` minors, `starlette` 1.7 → 1.9 and `litellm`.
  - Each fresh script environment (a uv cache clean, a new machine) builds a different builder.
  - `uv lock --script` locks the whole tree (151 entries in a scratch run). This is the builder's half of the CI/CD row; see GAPS.md.
- Not applicable at today's load: private mirrors, vendoring and forks.

## Proof
A: `uv pip compile --python-version <v>` with the builder's real pins:
```
builder on Python 3.11: No solution found ... openhands-sdk==1.54.0 depends on Python>=3.12
openhands-sdk==1.54.0 + litellm==1.50.0:    depends on litellm>=1.93.0 ... unsatisfiable
openhands-sdk==1.54.0 + pydantic==1.10.13:  depends on pydantic>=2.13.5 ... unsatisfiable
openhands-sdk==1.54.0 + httpx==0.23.0:      depends on httpx[socks]>=0.28.1 ... unsatisfiable
builder: 146 packages; adapter: 15 packages
```
B: the same pins resolved with `--exclude-newer 2026-10-12` and `2026-10-19` (17 of 146 changed). Selected:
```
fastapi: 0.143.0 -> 0.146.0      litellm: 1.105.0 -> 1.106.0     pillow: 12.3.0 -> 13.0.0
starlette: 1.7.0 -> 1.9.0        pydantic-settings: 2.15.0 -> 2.16.0
```
C: `uv lock --script` on a scratch copy of the script header wrote `agent_header.py.lock` with 151 entries, `litellm` fixed at 1.106.0.

## Related
006-ci-cd.md, 103-semantic-versioning.md, 107-build-caching.md, 067-secrets-management.md

## Sources
- "Our Software Dependency Problem", Russ Cox: https://research.swtch.com/deps
- "Dependency Resolution", pip documentation: https://pip.pypa.io/en/stable/topics/dependency-resolution/
