"""Alert rules at the factory's traffic: ~3 runs/day, a normal 25% of runs end failed or blocked.
Incident 1 (day 18): a broken dependency makes every run fail. Incident 2 (day 25): the adapter dies; no runs, no events.
Each rule is scored on false pages before day 18, minutes to detect each incident, and pages during them."""
import random

random.seed(4)
DAY = 1440
runs = []  # (minute, failed)
t = 0
while t < 30 * DAY:
    t += random.expovariate(3 / DAY)
    day = t / DAY
    if day >= 25:
        break  # the factory is dead: no more runs or events
    runs.append((t, True if day >= 18 else random.random() < 0.25))
alive_until = 25 * DAY  # alive_at stops updating here


def per_failure(rs):
    return [m for m, f in rs if f]


def consecutive(rs, n=3):
    pages, streak = [], 0
    for m, f in rs:
        streak = streak + 1 if f else 0
        if streak == n:
            pages.append(m)
    return pages


def ratio_24h(rs, threshold=0.5, min_runs=3):
    pages, last = [], -DAY
    for m, _ in rs:
        window = [f for mm, f in rs if m - DAY < mm <= m]
        if len(window) >= min_runs and sum(window) / len(window) > threshold and m - last > DAY:
            pages.append(m); last = m
    return pages


def score(name, pages, includes_staleness=False):
    false = sum(p < 18 * DAY for p in pages)
    i1 = [p for p in pages if 18 * DAY <= p < 25 * DAY]
    d1 = f"{(i1[0] - 18 * DAY) / 60:.0f} h" if i1 else "never"
    d2 = "5 min" if includes_staleness else "never (no events to alert on)"
    print(f"{name:<32} false pages {false:>2} | incident 1 detected after {d1:>8}, {len(i1):>2} pages | incident 2: {d2}")


print(f"simulated runs: {len(runs)}; normal failures before day 18: {sum(f for m, f in runs if m < 18 * DAY)}")
score("page on every failed run", per_failure(runs))
score("page on 3 failures in a row", consecutive(runs))
score("page on >50% failed in 24h", ratio_24h(runs))
score("3 in a row + alive_at stale 5 min", consecutive(runs), includes_staleness=True)
