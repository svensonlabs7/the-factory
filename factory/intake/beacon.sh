#!/usr/bin/env bash
# Stamp the factory's liveness off this machine, so the watchdog workflow notices when the Mac, the adapter or the
# network goes quiet. launchd runs it every 10 minutes (com.svenson.factory-beacon.plist). It stamps only while
# /health answers, so a dead adapter on a live Mac also goes stale.
set -euo pipefail
curl -fsS -m 10 -o /dev/null http://127.0.0.1:7654/health
gh variable set FACTORY_ALIVE_AT --body "$(date +%s)"
