#!/usr/bin/env bash
# Restart the adapter so it loads new code, but only while no run is in flight: a restart ends every in-flight run
# as error (_recover) and its build is lost. Usage: factory/intake/restart.sh [--force]
set -euo pipefail
pending=$(curl -fsS -m 10 http://127.0.0.1:7654/command/data | python3 -c 'import json, sys; print(json.load(sys.stdin)["limits"]["pending"])')
if [ "$pending" != 0 ] && [ "${1:-}" != --force ]; then
  echo "restart: $pending run(s) in flight. Try again when the dashboard shows none, or pass --force." >&2
  exit 1
fi
launchctl kickstart -k "gui/$(id -u)/com.svenson.factory-intake"
for _ in $(seq 1 30); do
  curl -fsS -m 2 -o /dev/null http://127.0.0.1:7654/health && { echo "restart: the adapter is back"; exit 0; }
  sleep 1
done
echo "restart: the adapter did not answer /health within 30 s; see .factory-logs/intake.err.log" >&2
exit 1
