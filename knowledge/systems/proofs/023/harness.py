"""Harness: run lp_app under uvicorn (real HTTP), then measure.
A. 8 state changes at seeded random times over 16 s. A short poller (every 1.0 s, a scaled-down 15 s dashboard poll)
   vs an async long poller (hold 4 s): requests made and how late each change was seen.
B. Starvation: 45 clients hold the sync long-poll (a `def` endpoint, run in the threadpool) vs the async one,
   then a plain `def` endpoint is timed."""
import asyncio
import random
import subprocess
import sys
import time

import httpx

PORT = 18790
BASE = f"http://127.0.0.1:{PORT}"


async def changes(client, times, seen_at):
    start = time.monotonic()
    for t in times:
        await asyncio.sleep(max(0, start + t - time.monotonic()))
        v = (await client.post(f"{BASE}/bump")).json()["version"]
        seen_at[v] = {"made": time.monotonic()}


async def short_poller(client, seen_at, stop, counter):
    version = 0
    while not stop.is_set():
        counter[0] += 1
        v = (await client.get(f"{BASE}/state")).json()["version"]
        for k in range(version + 1, v + 1):
            seen_at.setdefault(k, {}).setdefault("short", time.monotonic())
        version = v
        await asyncio.sleep(1.0)


async def long_poller(client, seen_at, stop, counter):
    version = 0
    while not stop.is_set():
        counter[0] += 1
        v = (await client.get(f"{BASE}/longpoll", params={"since": version}, timeout=10)).json()["version"]
        for k in range(version + 1, v + 1):
            seen_at.setdefault(k, {}).setdefault("long", time.monotonic())
        version = v


async def part_a():
    rng = random.Random(3)
    times = sorted(rng.uniform(0.5, 15.5) for _ in range(8))
    seen_at, stop = {}, asyncio.Event()
    short_n, long_n = [0], [0]
    async with httpx.AsyncClient() as client:
        tasks = [asyncio.create_task(short_poller(client, seen_at, stop, short_n)),
                 asyncio.create_task(long_poller(client, seen_at, stop, long_n))]
        await changes(client, times, seen_at)
        await asyncio.sleep(1.5)
        stop.set()
        await client.post(f"{BASE}/bump")  # release the held long poll
        await asyncio.gather(*tasks)
    for kind, n in (("short poll every 1 s", short_n[0]), ("long poll, hold 4 s", long_n[0])):
        key = "short" if kind.startswith("short") else "long"
        lags = [(seen_at[v][key] - seen_at[v]["made"]) * 1000 for v in range(1, 9)]
        print(f"A  {kind:<21}: {n:>3} requests in 17 s; change seen after mean {sum(lags) / 8:6.0f} ms, max {max(lags):6.0f} ms")


async def part_b(path):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=100), timeout=20) as client:
        holders = [asyncio.create_task(client.get(f"{BASE}/{path}", params={"since": 10_000})) for _ in range(45)]
        await asyncio.sleep(0.5)
        t = time.monotonic()
        await client.get(f"{BASE}/fast")
        took = (time.monotonic() - t) * 1000
        await asyncio.gather(*holders)
    print(f"B  45 clients holding /{path:<14}: a plain `def` request took {took:6.0f} ms")


server = subprocess.Popen([sys.executable, "-m", "uvicorn", "lp_app:app", "--port", str(PORT), "--log-level", "warning"])
for _ in range(100):
    try:
        httpx.get(f"{BASE}/fast")
        break
    except httpx.TransportError:
        time.sleep(0.1)
try:
    asyncio.run(part_a())
    asyncio.run(part_b("longpoll_sync"))
    asyncio.run(part_b("longpoll"))
finally:
    server.terminate()
