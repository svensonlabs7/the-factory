# 107. Build Caching

Track: E. Delivery and change · Status: proven · Updated: 2026-10-19

## What it is
A build cache stores the output of a build step (installed dependencies, compiled code, container layers, test results) under a key, and reuses it when the key matches instead of redoing the work. Everything depends on the key. A correct key is derived from every input that affects the output: source content, tool and compiler versions, flags, platform, environment. Bazel calls such a build hermetic.

A key that misses an input serves stale output: a "cache hit" that is wrong. A key that includes too much never hits. Keys from content hashes are safer than keys from timestamps or names.

A shared cache is also a trust boundary. Whoever can write an entry decides what later builds execute. GitHub Actions therefore lets low-trust triggers (`pull_request_target`, `workflow_run`, `issue_comment`) only read the default branch's caches. The docs warn that cache contents "aren't signed or verified".

## When it is worth it
Caching is worth it when a step is slow, repeated often, and depends on inputs that rarely change: dependency installs that take minutes, large compiles, image builds. Measure first. If restoring the cache costs about what the step costs, or the step is a few seconds of a job dominated by something else, a cache adds a correctness and security surface for nothing. Remote and shared build caches (Bazel, Gradle, Nx) are for large monorepos and many builders.

## How it fails
- **Incomplete key:** the key misses an input (tool version, platform, a file that changed without its timestamp changing) → a stale artifact is served as a hit, and the build "passes" with the wrong code.
- **Timestamp keys:** mtime-based invalidation misses changes that keep size and mtime (restored, copied or generated files) → old output runs.
- **Cache poisoning:** an untrusted job can write an entry that a trusted job restores and executes → code execution in the privileged context.
- **Secrets in cache paths:** a token lands in a cached directory → anyone who can read the cache, including PRs and forks, reads it.
- **Over-broad restore keys:** a partial match restores a cache built from different inputs → the result depends on whatever was cached last.
- **Cache as correctness crutch:** the build only works with a warm cache → a cold run (new runner, eviction after 7 days) fails.

## Review checklist
- [ ] **Does the cache key cover every input that affects the output?** · Applies when: the diff adds or changes a cache (`actions/cache`, a `setup-*` `cache:` option, a Docker cache, a tool's cache directory). · Block if: the key omits the lock file's hash, the tool or runtime version, or the platform the output depends on.
- [ ] **Can an untrusted run write what a trusted run restores?** · Applies when: the diff adds caching to a workflow triggered by `pull_request_target`, `workflow_run` or `issue_comment`, or by forks. · Block if: it sets `cache-mode: write` (or `write-only`) for such a trigger, or a privileged job executes cached files that a PR could have produced.
- [ ] **Is anything secret in a cached path?** · Applies when: the diff adds a cached path. · Block if: the path can contain credentials, tokens or `.env` files.
- [ ] **Does the build still pass cold?** · Applies when: the diff makes a step depend on cached state. · Block if: a run with an empty cache fails, instead of only being slower.
- [ ] **Is the cache worth it?** · Applies when: the diff adds a cache. · Block if: the cached step takes only a few seconds of a job dominated by other work, or no timing shows the saving.

## In the factory
- CI has no caches, and that is right. Step timings from the latest runs:
  - the gate jobs spend 4–5 s on `npm install -g @anthropic-ai/claude-code@2.1.296` in jobs of 9–43 s, dominated by the review itself (34 s for thermo-nuclear);
  - `tests` spends 6 s on `pip install` and 26 s on pytest;
  - `lint` spends 8 s on `pip install`.

  A cache restore costs seconds too, so caching would save little and would add a poisoning surface to `pull_request_target` (`.github/workflows/qa-gate.yml:5`).
- The factory's real caches are content-addressed, so their keys are their contents. Right:
  - the uv cache behind the builder's script environment and the adapter's `--with` environment;
  - the agent-server image, pinned by digest (`factory/build/run_agent.py:24`).

  What they do not fix is resolution drift: the key is what got resolved, not what was intended (108-dependency-hell.md).
- The adapter runs from a git working copy, and checkout sets mtimes to the checkout time, so the timestamp-pyc trap below needs a restore that preserves timestamps to bite. None happens in the factory today.
- Not applicable at today's load: `actions/cache`, remote build caches and Docker layer caching in CI.

## Proof
`/Users/labs/.local/bin/python3.11 -I scratchpad/mastery/107_build_cache.py` uses CPython's own bytecode cache (PEP 552). The source is changed to v2 with the same size and mtime, as a restored file keeps them:
```
A  key=TIMESTAMP    source now says v2 -> program prints 'v1' (first run 'v1')
B  key=CHECKED_HASH source now says v2 -> program prints 'v2' (first run 'v1')
```
The timestamp key serves stale bytecode as a cache hit. The content-hash key catches the change. (On Apple's `/usr/bin/python3`, A printed `v2`, because that build writes bytecode under a separate `sys.pycache_prefix`, so the hand-compiled `.pyc` was never read.)

CI timings: `gh run view <id> --json jobs` for the latest `qa-gate`, `tests` and `static` runs.

## Related
108-dependency-hell.md, 006-ci-cd.md, 002-caching.md, 067-secrets-management.md, 103-semantic-versioning.md

## Sources
- "Dependency caching reference", GitHub Actions documentation: https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- PEP 552, "Deterministic pycs": https://peps.python.org/pep-0552/
