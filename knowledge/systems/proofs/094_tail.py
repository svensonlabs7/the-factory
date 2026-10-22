"""Tail latency (seeded simulation, 100,000 user requests each).
A. Fan-out amplification: each server answers in 10 ms but 1 request in 100 takes 1 s. A user request that waits for
   N servers is slow whenever any of them is.
B. Hedged requests (Dean & Barroso): send a second copy to another replica once the first has been outstanding past
   the 95th-percentile latency; use whichever answers first.
C. The factory's gate is a fan-out of review jobs; its latency is the slowest job (real CI data, passed in)."""
import json
import random
import statistics
import sys

rng = random.Random(11)


def server():
    return 1000.0 if rng.random() < 0.01 else rng.uniform(5, 15)


def pct(xs, p):
    xs = sorted(xs)
    return xs[int(p / 100 * (len(xs) - 1))]


for n in (1, 10, 100):
    slow = sum(max(server() for _ in range(n)) >= 1000 for _ in range(20_000)) / 20_000
    print(f"A  fan-out to {n:>3} servers: {slow:6.1%} of user requests take 1 s (formula 1-0.99^N = {1 - 0.99 ** n:6.1%})")

single = [server() for _ in range(100_000)]
hedge_after = pct(single, 95)
hedged, extra = [], 0
for _ in range(100_000):
    first = server()
    if first > hedge_after:
        extra += 1
        first = min(first, hedge_after + server())
    hedged.append(first)
print(f"B  no hedging:              p50 {pct(single, 50):6.1f} ms  p99 {pct(single, 99):7.1f} ms  p99.9 {pct(single, 99.9):7.1f} ms")
print(f"B  hedge after p95 ({hedge_after:.1f} ms): p50 {pct(hedged, 50):6.1f} ms  p99 {pct(hedged, 99):7.1f} ms  p99.9 {pct(hedged, 99.9):7.1f} ms; extra requests {extra / 1000:.1f}%")

runs = json.loads(sys.argv[1])
gate = [max(r.values()) for r in runs]
slowest = [max(r, key=r.get) for r in runs]
second = [sorted(r.values())[-2] for r in runs]
print(f"C  {len(runs)} qa-gate runs: gate time = slowest job, median {statistics.median(gate)} s, max {max(gate)} s; slowest job thermo-nuclear in {slowest.count('thermo-nuclear')}/{len(runs)}; second-slowest median {statistics.median(second)} s")
