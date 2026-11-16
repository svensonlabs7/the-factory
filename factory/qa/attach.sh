#!/usr/bin/env bash
# Usage: factory/qa/attach.sh owner/name
# Opens a PR in that repo adding the QA gate's caller workflow (caller.yml), pinned to this repo's current main.
# Merge it, then run factory/qa/protect.sh, and set the repo's CLAUDE_CODE_OAUTH_TOKEN secret (`gh secret set`).
set -euo pipefail
repo=${1:?usage: attach.sh owner/name}
[[ $repo =~ ^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] || { echo "attach: not an owner/name: $repo" >&2; exit 2; }
here=$(cd "$(dirname "$0")" && pwd)
sha=$(gh api repos/svensonlabs7/the-factory/commits/main --jq .sha)
base=$(gh repo view "$repo" --json defaultBranchRef --jq .defaultBranchRef.name)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
gh repo clone "$repo" "$work/repo" -- --quiet --depth 1
cd "$work/repo"
git checkout -q -b factory/attach-gate
mkdir -p .github/workflows
sed -e "s/__SHA__/$sha/g" -e "s/__BRANCH__/$base/g" "$here/caller.yml" > .github/workflows/qa-gate.yml
git add .github/workflows/qa-gate.yml
git commit -q -m "Add the factory's QA gate"
git push -q origin factory/attach-gate
gh pr create --repo "$repo" --base "$base" --head factory/attach-gate --title "Add the factory's QA gate" \
  --body "Adds the caller for the factory's QA gate, pinned to svensonlabs7/the-factory@$sha. Merge it, then run factory/qa/protect.sh to require the checks."
