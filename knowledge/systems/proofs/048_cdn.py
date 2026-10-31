"""CDN offload (seeded simulation, 10 minutes): requests spread over edge POPs, each POP caching an object for its TTL.
A. One hot asset at 1,000 req/s across 300 POPs, TTL 60 s: origin fetches with and without a tiered (upper) cache.
B. A long tail: 100,000 distinct objects (Zipf) at the same 1,000 req/s: most objects are rare per POP, so the hit
   ratio is far lower than for one hot asset."""
import random

rng = random.Random(6)
SECONDS, RATE, POPS, TTL = 600, 1000, 300, 60


def simulate(keys, tiered):
    edge, upper, origin, n = {}, {}, 0, 0
    weights = [1 / (i + 1) ** 1.0 for i in range(keys)]
    picks = rng.choices(range(keys), weights=weights, k=SECONDS * RATE) if keys > 1 else [0] * (SECONDS * RATE)
    for i, key in enumerate(picks):
        t = i / RATE
        pop = rng.randrange(POPS)
        if edge.get((pop, key), -1e9) + TTL > t:
            continue
        edge[(pop, key)] = t
        if tiered:
            if upper.get(key, -1e9) + TTL > t:
                continue
            upper[key] = t
        origin += 1
    return origin, len(picks)


for name, keys in (("one hot asset", 1), ("100,000-object long tail", 100_000)):
    for tiered in (False, True):
        origin, total = simulate(keys, tiered)
        print(f"{'A' if keys == 1 else 'B'}  {name:<26} {'tiered' if tiered else 'edge only':<9}: origin fetches {origin:>7,} of {total:,} requests -> hit ratio {1 - origin / total:6.2%}")
