#!/usr/bin/env bash
# Restart the adapter so it loads new code, but only while no run is in flight: a restart ends every in-flight run
# as error (_recover) and its build is lost. Usage: factory/intake/restart.sh [--force]
# --force restarts without asking, including an adapter that is down or not answering.
set -euo pipefail
if [ "${1:-}" != --force ]; then
  if ! pending=$(curl -fsS -m 10 http://127.0.0.1:7654/health | python3 -c 'import json, sys; print(json.load(sys.stdin)["pending"])'); then
    echo "restart: the adapter is not answering, so in-flight runs cannot be checked. Pass --force to restart anyway." >&2
    exit 1
  fi
  if [ "$pending" != 0 ]; then
    echo "restart: $pending run(s) in flight. Try again when the dashboard shows none, or pass --force." >&2
    exit 1
  fi
fi
launchctl kickstart -k "gui/$(id -u)/com.svenson.factory-intake"
for _ in $(seq 1 30); do
  curl -fsS -m 2 -o /dev/null http://127.0.0.1:7654/health && { echo "restart: the adapter is back"; exit 0; }
  sleep 1
done
echo "restart: the adapter did not answer /health within 30 s; see .factory-logs/intake.err.log" >&2
exit 1
