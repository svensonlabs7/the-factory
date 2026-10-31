"""Throughput.
A. Goodput under overload (discrete-event simulation): one server, 10 ms per request (capacity 100 req/s), clients
   give up after 1 s. A FIFO queue keeps working on requests whose clients have left; shedding rejects a request
   at arrival when its queue wait would exceed 100 ms.
B. The real adapter's /health throughput on a scratch uvicorn (this working copy, scratch FACTORY_ROOT), by client
   concurrency.
C. The factory's pipeline through Little's law, from the live run records (L = lambda * W)."""
import asyncio
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import httpx

REPO = sys.argv[1]


def simulate(rate, shed, seconds=60, service=0.010, timeout=1.0, max_wait=0.1):
    t, free_at, sent, done_in_time, done = 0.0, 0.0, 0, 0, 0
    gap = 1.0 / rate
    while t < seconds:
        sent += 1
        start = max(t, free_at)
        if shed and start - t > max_wait:                 # keep the queue short: reject at arrival
            t += gap
            continue                                   # rejected fast, costs nothing
        free_at = start + service
        if free_at <= seconds:                         # completed inside the measured window
            done += 1
            done_in_time += (free_at - t) <= timeout
        t += gap
    return done / seconds, done_in_time / seconds


for rate in (50, 100, 150, 200):
    fifo, shed = simulate(rate, False), simulate(rate, True)
    print(f"A  offered {rate:>3}/s: FIFO throughput {fifo[0]:5.1f}/s goodput {fifo[1]:5.1f}/s | shedding throughput {shed[0]:5.1f}/s goodput {shed[1]:5.1f}/s")

root = tempfile.mkdtemp()
shutil.copy(os.path.join(REPO, "HEARTBEAT.template.md"), os.path.join(root, "HEARTBEAT.template.md"))
server = subprocess.Popen(["uv", "run", "-q", "--python", "3.11", "--with", "fastapi", "--with", "uvicorn", "--", "uvicorn",
                           "factory.intake.webhook_adapter:app", "--port", "18810", "--log-level", "warning"],
                          cwd=REPO, env={**os.environ, "FACTORY_ROOT": root, "FACTORY_WEBHOOK_SECRET": "scratch"})
for _ in range(200):
    try:
        httpx.get("http://127.0.0.1:18810/health")
        break
    except httpx.TransportError:
        time.sleep(0.05)


async def load(concurrency, total=3000):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=concurrency)) as c:
        sem = asyncio.Semaphore(concurrency)

        async def one():
            async with sem:
                await c.get("http://127.0.0.1:18810/health")

        t = time.perf_counter()
        await asyncio.gather(*(one() for _ in range(total)))
        return total / (time.perf_counter() - t)

try:
    for conc in (1, 8, 32):
        print(f"B  /health, {conc:>2} concurrent clients: {asyncio.run(load(conc)):7.0f} req/s")
finally:
    server.terminate()
    shutil.rmtree(root)

runs = [json.load(open(p)) for p in glob.glob(os.path.join(REPO, ".factory-logs", "*.meta.json"))]
timed = [r for r in runs if isinstance(r.get("queued_at"), (int, float)) and r.get("finished_at")]
span_days = (max(r["queued_at"] for r in timed) - min(r["queued_at"] for r in timed)) / 86400
lam = len(timed) / max(span_days, 1e-9)
w = sum(r["finished_at"] - r["queued_at"] for r in timed) / len(timed)
print(f"C  {len(timed)} timed runs over {span_days:.1f} days: lambda {lam:.1f} runs/day, mean time in system W {w / 60:.1f} min, L = lambda*W = {lam * w / 86400:.3f} runs in flight on average")
print(f"C  one worker at W per run caps throughput at {86400 / w:.0f} runs/day; the configured cap is 30/day, so the worker is busy {30 * w / 86400:.0%} at the cap")
