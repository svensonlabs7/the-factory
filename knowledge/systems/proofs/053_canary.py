"""Canary releases, simulated (seeded).
A. Blast radius: a bad release (0.1% -> 2% errors) at 10,000 req/min, deployed to everyone vs to a 5% canary that is
   compared with the control every minute and rolled back on a significant difference.
B. Concurrent control vs before/after: a good release ships as peak load raises everyone's error rate.
C. The factory's volume: how many runs a canary needs to see a failure rate go from 25% (the 8 live run records)
   to 50%, and how many days that takes at 3 runs a day."""
import math
import random

rng = random.Random(7)


def errors(n, p):
    return sum(rng.random() < p for _ in range(n))


def z(e1, n1, e2, n2):  # two-proportion z statistic, canary minus control
    p = (e1 + e2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    return (e1 / n1 - e2 / n2) / se


def blast_radius():
    rate, good, bad = 10_000, 0.001, 0.02
    # Everyone at once: the fleet alarm fires on 1% errors over a minute, then rollback takes 5 minutes.
    hurt, minute = 0, 0
    while True:
        minute += 1
        e = errors(rate, bad)
        hurt += e
        if e / rate > 0.01:
            hurt += sum(errors(rate, bad) for _ in range(5))
            break
    print(f"A  deploy to all:  {hurt:,} failed requests (alarm after {minute} min, 5 min to roll back)")
    canary_n, control_n, ce, ke, minute = 0, 0, 0, 0, 0
    while True:
        minute += 1
        cn = rate * 5 // 100
        canary_n, control_n = canary_n + cn, control_n + rate - cn
        ce += errors(cn, bad)
        ke += errors(rate - cn, good)
        if z(ce, canary_n, ke, control_n) > 3:
            break
    extra = ce - round(canary_n * good)
    print(f"A  5% canary:      {extra:,} failed requests caused by the release (caught at minute {minute}, {canary_n:,} canary requests)")


def control_vs_before_after():
    n = 20_000
    before = errors(n, 0.001)                  # off-peak, old version everywhere
    canary, control = errors(n, 0.004), errors(n, 0.004)  # peak: new (good) canary and old control both see 0.4%
    print(f"B  good release at peak, before/after: z = {z(canary, n, before, n):.1f} -> {'rolled back for nothing' if z(canary, n, before, n) > 3 else 'passes'}")
    print(f"B  good release at peak, vs control:  z = {z(canary, n, control, n):.1f} -> {'rolled back' if z(canary, n, control, n) > 3 else 'passes'}")


def low_volume():
    p0, p1 = 2 / 8, 0.5
    for n in (5, 10, 20, 40, 60, 80):
        hits = sum(z(errors(n, p1), n, errors(n, p0), n) > 1.645 for _ in range(2000))
        print(f"C  {n:>2} runs per arm ({2 * n / 3:5.1f} days at 3 runs/day): regression detected {hits / 2000:.0%} of the time")


blast_radius()
control_vs_before_after()
low_volume()
