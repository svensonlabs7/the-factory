"""Exponential backoff and jitter, after Brooker's contention simulation.
N clients start together and need one exclusive write each. Time runs in 1 ms slots: if exactly one client
tries in a slot it succeeds; if several try, all collide and fail (like optimistic concurrency).
Each failed client waits per its strategy, then tries again. Measure total attempts and time to finish."""
import random

N, BASE, CAP, GIVE_UP_MS = 50, 2, 1000, 120_000


def none(attempt, prev):
    return 1


def expo(attempt, prev):
    return min(CAP, BASE * 2 ** attempt)


def full_jitter(attempt, prev):
    return random.uniform(0, min(CAP, BASE * 2 ** attempt))


def equal_jitter(attempt, prev):
    t = min(CAP, BASE * 2 ** attempt)
    return t / 2 + random.uniform(0, t / 2)


def decorrelated(attempt, prev):
    return min(CAP, random.uniform(BASE, prev * 3))


def simulate(strategy, seed):
    random.seed(seed)
    clients = {c: {"at": 0, "attempt": 0, "sleep": BASE} for c in range(N)}
    attempts = 0
    while clients:
        slot = min(c["at"] for c in clients.values())
        if slot > GIVE_UP_MS:
            return attempts, None, len(clients)
        trying = [k for k, c in clients.items() if c["at"] == slot]
        attempts += len(trying)
        if len(trying) == 1:
            del clients[trying[0]]
            continue
        for k in trying:
            c = clients[k]
            c["sleep"] = strategy(c["attempt"], c["sleep"])
            c["attempt"] += 1
            c["at"] = slot + max(1, round(c["sleep"]))
    return attempts, slot, 0


print(f"{N} clients, base {BASE} ms, cap {CAP} ms, give up at {GIVE_UP_MS // 1000} s; median of 5 seeds\n")
print(f"{'strategy':<16}{'attempts':>10}{'finished in':>14}")
for name, s in (("no backoff", none), ("exponential", expo), ("full jitter", full_jitter),
                ("equal jitter", equal_jitter), ("decorrelated", decorrelated)):
    runs = sorted(simulate(s, seed) for seed in range(5))
    attempts, done_ms, stuck = runs[2]
    done = f"{done_ms / 1000:.2f} s" if done_ms is not None else f"never ({stuck} stuck)"
    print(f"{name:<16}{attempts:>10}{done:>14}")
