"""SLO targets at the factory's volume. Standard library only.
A. How precisely does 5 of 8 (the real autonomous-delivery SLI) pin down the true rate? Wilson 95% interval.
B. At ~60 runs/month, what does each target allow, and can a month's number tell 'meets 90%' from 'is really 85%'?"""
import math
import random


def wilson(k, n, z=1.96):
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


for k, n in ((5, 8), (48, 60), (480, 600)):
    lo, hi = wilson(k, n)
    print(f"A  {k}/{n} = {k / n:.0%}: the true rate is somewhere in {lo:.0%}..{hi:.0%} (95%)")

runs = 60
for target in (0.80, 0.90, 0.99, 0.999):
    print(f"B  target {target:.1%} over {runs} runs/month allows {runs * (1 - target):.1f} misses a month")

random.seed(1)
months = 10000
for true_rate in (0.85, 0.92):
    passed = sum(sum(random.random() < true_rate for _ in range(runs)) / runs >= 0.90 for _ in range(months))
    print(f"B  true rate {true_rate:.0%}, SLO 90%: the month's number says 'met' in {passed / months:.0%} of months")
