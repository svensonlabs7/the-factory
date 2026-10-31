"""A. Cross-Site WebSocket Hijacking: a page on another origin opens a socket; the browser attaches the operator's
   cookie (simulated by sending it). Without an Origin check the socket opens and data flows; with one it is refused.
B. Dead peers: a client connects, then is frozen with SIGSTOP (as a laptop lid closing or a half-open TCP link).
   With uvicorn's WebSocket pings off, the server keeps the connection; with pings every 1 s and a 1 s timeout,
   it closes it."""
import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import time

import websockets

PORT = 18800
COOKIE = {"Cookie": "session=operator"}


def start(ping):
    log = tempfile.mktemp()
    env = {**os.environ, "WS_LOG": log}
    args = ["--ws-ping-interval", "1", "--ws-ping-timeout", "1"] if ping else ["--ws-ping-interval", "0"]
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "ws_app:app", "--port", str(PORT), "--log-level", "warning", *args], env=env)
    time.sleep(2.5)
    return proc, log


async def hijack(path):
    try:
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/{path}", additional_headers={**COOKIE, "Origin": "https://evil.example"}) as ws:
            return f"opened, read {await ws.recv()!r}"
    except websockets.exceptions.InvalidStatus as exc:
        return f"refused: HTTP {exc.response.status_code}"


CLIENT = f"""
import asyncio, websockets
async def main():
    async with websockets.connect("ws://127.0.0.1:{PORT}/ws", additional_headers={{"Cookie": "session=operator", "Origin": "https://dash.svensonlabs.dev"}}, ping_interval=None) as ws:
        while True:
            await asyncio.sleep(3600)
asyncio.run(main())
"""


def frozen_client(ping):
    proc, log = start(ping)
    client = subprocess.Popen([sys.executable, "-c", CLIENT])
    time.sleep(1.0)
    os.kill(client.pid, signal.SIGSTOP)        # the client stops answering, but its socket stays open
    time.sleep(6.0)
    lines = open(log).read().split()
    os.kill(client.pid, signal.SIGKILL)
    proc.terminate()
    proc.wait()
    return f"open {lines.count('open')}, closed by the server within 6 s: {lines.count('closed')}"


proc, _ = start(ping=True)
try:
    print(f"A  evil.example -> /ws (cookie only):          {asyncio.run(hijack('ws'))}")
    print(f"A  evil.example -> /ws_checked (Origin allowlist): {asyncio.run(hijack('ws_checked'))}")
finally:
    proc.terminate()
    proc.wait()
print(f"B  pings off, client frozen:  {frozen_client(ping=False)}")
print(f"B  pings 1 s, timeout 1 s:    {frozen_client(ping=True)}")
