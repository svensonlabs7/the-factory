"""A small FastAPI app with short-poll, async long-poll and sync (threadpool) long-poll endpoints."""
import asyncio
import time

from fastapi import FastAPI

app = FastAPI()
state = {"version": 0, "changed": None}
HOLD = 4.0


async def _cond():
    if state["changed"] is None:
        state["changed"] = asyncio.Condition()
    return state["changed"]


@app.post("/bump")
async def bump():
    cond = await _cond()
    async with cond:
        state["version"] += 1
        cond.notify_all()
    return {"version": state["version"]}


@app.get("/state")
async def short(since: int = 0):
    return {"version": state["version"]}


@app.get("/longpoll")
async def longpoll(since: int = 0):
    cond = await _cond()
    async with cond:
        try:
            await asyncio.wait_for(cond.wait_for(lambda: state["version"] > since), HOLD)
        except asyncio.TimeoutError:
            pass
    return {"version": state["version"]}


@app.get("/longpoll_sync")
def longpoll_sync(since: int = 0):
    end = time.monotonic() + HOLD
    while state["version"] <= since and time.monotonic() < end:
        time.sleep(0.05)
    return {"version": state["version"]}


@app.get("/fast")
def fast():
    return {"ok": True}
