#!/usr/bin/env bash
# Usage: factory/qa/protect.sh owner/name
# Requires the gate's three lanes on that repo's default branch, up to date, for everyone including admins, so
# nothing merges except through a PR that passed them. Run it after attach.sh's PR is merged: the checks must
# exist before they can be required. Add the repo's own test check with `gh api` if it has one.
set -euo pipefail
repo=${1:?usage: protect.sh owner/name}
[[ $repo =~ ^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] || { echo "protect: not an owner/name: $repo" >&2; exit 2; }
base=$(gh repo view "$repo" --json defaultBranchRef --jq .defaultBranchRef.name)
gh api -X PUT "repos/$repo/branches/$base/protection" --input - <<'JSON' >/dev/null
{
  "required_status_checks": {"strict": true, "contexts": ["gate / thermo-nuclear", "gate / ponytail-review", "gate / ux-laws"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
echo "protect: $repo@$base now requires gate / thermo-nuclear, gate / ponytail-review and gate / ux-laws"
