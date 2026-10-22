"""WebSocket app: /ws sends the caller's run data, authenticated by a session cookie (as Cloudflare Access's would be).
/ws_checked also requires an allowed Origin. Every open/close is appended to events.log."""
import asyncio
import os
import time

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

app = FastAPI()
ALLOWED = {"https://dash.svensonlabs.dev"}
LOG = os.environ["WS_LOG"]


def note(text):
    with open(LOG, "a") as f:
        f.write(f"{time.monotonic():.2f} {text}\n")


async def serve(ws: WebSocket, check_origin: bool):
    if ws.cookies.get("session") != "operator":
        await ws.close(code=1008)
        return
    if check_origin and ws.headers.get("origin") not in ALLOWED:
        await ws.close(code=1008)  # refused before accept: the handshake fails with 403
        note(f"refused origin {ws.headers.get('origin')}")
        return
    await ws.accept()
    note("open")
    try:
        await ws.send_text("run 920d7293: completed, PR #56")
        while True:
            await asyncio.sleep(0.2)
            await ws.send_text("tick")
    except (WebSocketDisconnect, RuntimeError, Exception):
        pass
    finally:
        note("closed")


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await serve(ws, check_origin=False)


@app.websocket("/ws_checked")
async def ws_checked(ws: WebSocket):
    await serve(ws, check_origin=True)
