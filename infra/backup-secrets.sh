#!/usr/bin/env bash
# Back up the secrets a rebuild needs and git does not hold: .env and the tunnel credentials. Writes one AES-256
# encrypted disk image; keep it off this machine (a password manager attachment, or a drive stored elsewhere).
# Usage: infra/backup-secrets.sh <output.dmg>     Asks for a passphrase. Restore steps: infra/README.md.
set -euo pipefail
out=${1:?usage: infra/backup-secrets.sh <output.dmg>}
root=${FACTORY_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/cloudflared"
cp "$root/.env" "$stage/env"
cp "$HOME"/.cloudflared/*.json "$HOME/.cloudflared/cert.pem" "$stage/cloudflared/"
# At a terminal hdiutil asks for the passphrase without echoing it; from a pipe it reads stdin.
stdinpass=$([ -t 0 ] || echo -stdinpass)
hdiutil create -quiet -encryption AES-256 $stdinpass -srcfolder "$stage" -volname factory-secrets "$out"
echo "wrote $out: .env and $(find "$stage/cloudflared" -type f | wc -l | tr -d ' ') tunnel files. Store it off this machine."
