"""A minimal EventSource over httpx: parses id/data/retry, reconnects after `retry` ms, sends Last-Event-ID."""
import subprocess
import sys
import time

import httpx

PORT = 18795


def listen(ids, seconds=4.5):
    got, last_id, retry, reconnects = [], None, 1000, -1
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        reconnects += 1
        headers = {"Last-Event-ID": last_id} if last_id else {}
        with httpx.stream("GET", f"http://127.0.0.1:{PORT}/events", params={"ids": ids}, headers=headers, timeout=5) as r:
            event = {}
            for line in r.iter_lines():
                if line == "":
                    if "data" in event:
                        got.append(int(event["data"].split()[-1]))
                    if "id" in event:
                        last_id = event["id"]
                    event = {}
                elif not line.startswith(":") and ":" in line:
                    field, value = line.split(":", 1)
                    event[field] = value.lstrip()
                    if field == "retry" and value.strip().isdigit():
                        retry = int(value)
        time.sleep(retry / 1000 + 0.15)  # reconnection delay (+ a little extra downtime)
    return got, reconnects


server = subprocess.Popen([sys.executable, "-m", "uvicorn", "sse_app:app", "--port", str(PORT), "--log-level", "warning"])
for _ in range(100):
    try:
        httpx.get(f"http://127.0.0.1:{PORT}/docs")
        break
    except httpx.TransportError:
        time.sleep(0.1)
try:
    for ids in (0, 1):
        got, reconnects = listen(ids)
        missing = sorted(set(range(min(got), max(got) + 1)) - set(got))
        label = "id + Last-Event-ID" if ids else "no id field"
        print(f"{'B' if ids else 'A'}  {label:<19}: {reconnects} reconnects, received {got}, missed {missing}")
        time.sleep(0.5)
finally:
    server.terminate()
