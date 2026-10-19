# 67. Secrets Management

Track: B. Security · Status: proven · Updated: 2026-10-18

## What it is
Secrets are the values that grant access: API keys, OAuth tokens, signing secrets, passwords. Managing them means:
- keeping them out of source control and logs;
- giving each process only the secrets it needs;
- injecting them at runtime;
- rotating them on a schedule and at once after any exposure;
- scanning for leaks before they leave your control, not after.

The OWASP rule for a leak is to revoke first, then rotate, then clean up. Every place a secret can flow is a channel to guard: environment variables are inherited by child processes and can show up in logs and dumps, CI jobs print output, and anything a process writes can carry a secret it was able to read.

## When it is worth it
Always, at any scale, for any credential. The minimum is no secrets in git (ignored files plus a scanner), owner-only file permissions, least privilege per process, a rotation path, and a secret scan in front of every publish step: push, release, artifact upload. Central managers (Vault, AWS Secrets Manager), dynamic short-lived credentials and automated rotation pay off with many services and many people. For one operator on one host, a mode-600 `.env` is reasonable.

## How it fails
- **Committed secret:** a key lands in git → it is public for good on a public repo, and still in history after deletion.
- **Scan after publish:** the leak scanner runs in CI after the push → the secret is already public when the check goes red.
- **Overshared secret:** every process or job gets every secret → one compromise exposes all of them.
- **Secret in logs or artifacts:** a debug line, an error message or an uploaded report contains the value → anyone who can read logs has it.
- **Untrusted code next to secrets:** a privileged CI trigger (`pull_request_target`) checks out and runs PR code → the PR author can read the secrets.
- **No rotation path:** changing a secret breaks every client at once → nobody rotates, even after a leak.

## Review checklist
- [ ] **Is every new secret kept out of git, code and logs?** · Applies when: the diff adds a credential, key or token, or code that handles one. · Block if: the value appears in a tracked file, a default, a log or error message, or a command-line argument.
- [ ] **Is every publish step scanned before it publishes?** · Applies when: the diff adds a step that pushes commits, uploads artifacts or posts output others can read, or makes an existing step publish new agent-produced content. · Block if: that content is published with no secret scan first.
- [ ] **Does each process or job get only the secrets it needs?** · Applies when: the diff passes secrets to a process, container or CI job. · Block if: it passes a secret that process does not use, or passes all of them as a group.
- [ ] **Does a privileged CI job keep untrusted code away from secrets?** · Applies when: the diff adds or edits a `pull_request_target` or `workflow_run` workflow, or a job with secrets. · Block if: it checks out or runs PR code, or interpolates PR-controlled text into a `run:` script, while secrets are available.
- [ ] **Can the secret be rotated without an outage?** · Applies when: the diff adds a secret that verifies or signs requests. · Block if: only one value can be valid at a time.

## In the factory
- `.env`: git-ignored, mode `600`, holding the 4 secrets. A scan of all git history and `.factory-logs` found no token-shaped strings, and the launchd plist carries only `PATH` and `HOME`. Right.
- `.github/workflows/static.yml:33`: gitleaks 8.30.1, checksum-pinned, scans every commit a PR reaches, with `--redact`. Right, but it runs after the push (gap below).
- `.github/workflows/qa-gate.yml`: `pull_request_target` runs main's copy, rejects fork PRs, never checks out PR code (it fetches the head as a ref and reads it with `git show`), limits the reviewer's tools, and tells it the PR is untrusted data. All workflows default to `contents: read`. Right.
- `factory/build/run_agent.py:42`: the sandbox gets one secret, `CLAUDE_CODE_OAUTH_TOKEN`, which the agent needs, and no GitHub credentials. Its network reaches only an allow-list (egress.sh). Right.
- `factory/intake/webhook_adapter.py:49`: the webhook secret can rotate with a previous value accepted. Right.
- Gap (high): the agent holds the Claude token, and its commits leave the sandbox through the adapter's `git push` with no scan first. The repo is public, so a leaked token is published before gitleaks in CI fails the check (see GAPS.md).
- Not verified: whether a prompt-injected reviewer in the gate could read its own environment and write the token into `review.md`, which is uploaded as an artifact on a public repo. GitHub masks registered secrets in logs, but artifacts are not masked.
- Acceptable: `actions/checkout@v4` and `actions/upload-artifact@v4` are pinned to tags, not SHAs. GitHub's guidance allows tags from a creator you trust, and these are GitHub's own.

## Proof
`pytest -s scratchpad/mastery/067_secrets.py`, against the real adapter through `tests/test_adapter.py`'s fixture, with an agent that commits a fake, randomly generated Anthropic-format key:
```
1  run completed; origin's factory/2b123478 has debug.log carrying the fake key: True
2  gitleaks on that commit: exit 1, findings [('anthropic-api-key', 'debug.log')]
```
The adapter pushed it, and the run completed. `gitleaks` is installed on this host (`/opt/homebrew/bin/gitleaks`), so the same scan could run in `_push` before `git push`. `gh repo view` reports the repo's visibility as `PUBLIC`.

## Related
101-webhooks.md, 068-iam.md, 070-jwt-rotation.md, 059-logging.md, 006-ci-cd.md, 069-oauth.md, 080-ssrf.md, 078-sql-injection.md, 103-semantic-versioning.md, 107-build-caching.md, 108-dependency-hell.md, 028-connection-pooling.md

## Sources
- "Secrets Management Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- "Security hardening for GitHub Actions", GitHub Docs: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
