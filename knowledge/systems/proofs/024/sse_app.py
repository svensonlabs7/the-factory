"""SSE app: events 1..N are produced every 0.3 s into a buffer. /events streams them as text/event-stream.
With ?ids=1 each event carries `id:` and a reconnect resumes after Last-Event-ID; without it a reconnect starts
from "now". The server drops each connection after 1 s, as a proxy or deploy would."""
import asyncio
import time

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
STARTS = {}  # the producer's clock starts at each mode's first request
TOTAL, EVERY = 12, 0.3


def produced(ids):
    return min(TOTAL, int((time.monotonic() - STARTS.setdefault(ids, time.monotonic())) / EVERY))


@app.get("/events")
async def events(request: Request, ids: int = 0):
    last = request.headers.get("last-event-id")
    nxt = int(last) + 1 if (ids and last) else produced(ids) + 1

    async def stream():
        nonlocal nxt
        yield "retry: 200\n\n"
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            while nxt <= produced(ids):
                yield (f"id: {nxt}\n" if ids else "") + f"data: event {nxt}\n\n"
                nxt += 1
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
