#!/usr/bin/env bash
# Stamp the factory's liveness off this machine, so the watchdog workflow notices when the Mac, the adapter or the
# network goes quiet. launchd runs it every 10 minutes (com.svenson.factory-beacon.plist). It stamps only while
# /ready answers 200, so a dead adapter, or one that cannot ship (Docker down, gh logged out, no token, full disk), also
# goes stale.
set -euo pipefail
curl -fsS -m 30 -o /dev/null http://127.0.0.1:7654/ready
gh variable set FACTORY_ALIVE_AT --body "$(date +%s)"
