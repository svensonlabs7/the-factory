#!/usr/bin/env bash
# Install the factory host's service config from this repo, or check that the installed copies still match it.
# Usage: infra/install.sh [--check]
#   --check   change nothing; list each installed file as ok, DRIFT or MISSING, and exit 1 unless all are ok.
# Without --check it copies any file that differs and reloads only what it changed, so a second run is a no-op.
# Secrets are not handled here: restore .env and ~/.cloudflared/<tunnel-id>.json + cert.pem first (infra/README.md).
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
agents=$HOME/Library/LaunchAgents
uid=$(id -u)
# repo file | installed path | launchd label to reload (or the label whose program reads the file)
pairs=(
  "infra/cloudflare-tunnel/config.yml|$HOME/.cloudflared/config.yml|com.cloudflare.cloudflared"
  "infra/cloudflare-tunnel/com.cloudflare.cloudflared.plist|$agents/com.cloudflare.cloudflared.plist|com.cloudflare.cloudflared"
  "factory/intake/com.svenson.factory-intake.plist|$agents/com.svenson.factory-intake.plist|com.svenson.factory-intake"
  "factory/intake/com.svenson.factory-beacon.plist|$agents/com.svenson.factory-beacon.plist|com.svenson.factory-beacon"
)
check=${1:-}
bad=0
for pair in "${pairs[@]}"; do
  IFS='|' read -r src dst label <<<"$pair"
  if [ ! -e "$dst" ]; then state=MISSING; elif cmp -s "$repo/$src" "$dst"; then state=ok; else state=DRIFT; fi
  echo "$state  $dst"
  [ "$state" = ok ] && continue
  if [ "$check" = --check ]; then bad=1; continue; fi
  mkdir -p "$(dirname "$dst")"
  cp "$repo/$src" "$dst"
  if [[ $dst == *.plist ]]; then  # a changed plist only takes effect when launchd reloads it
    launchctl bootout "gui/$uid/$label" 2>/dev/null || true
    launchctl bootstrap "gui/$uid" "$dst"
  elif launchctl print "gui/$uid/$label" >/dev/null 2>&1; then  # restart only a loaded service; on a fresh host
    launchctl kickstart -k "gui/$uid/$label"                    # its plist's own row loads it, reading this file
  fi
  echo "   installed and reloaded $label"
done
exit "$bad"
