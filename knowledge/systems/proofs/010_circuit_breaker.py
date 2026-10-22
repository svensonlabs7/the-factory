"""Circuit breaker, in simulated time. A caller sends 10 requests a second for 80 s to a dependency that is
healthy (0-10 s), hung until the 2 s timeout (10-40 s), failing half its calls fast (40-60 s), then healthy.
Breaker: opens after 5 consecutive failures, stays open 5 s, then lets one trial call through (half-open)."""
import random

TIMEOUT, OPEN_FOR, THRESHOLD = 2.0, 5.0, 5
PHASES = [("healthy", 0, 10), ("hung", 10, 40), ("half failing", 40, 60), ("recovered", 60, 80)]


def dependency(t):
    """Returns (ok, seconds the caller waited)."""
    if 10 <= t < 40:
        return False, TIMEOUT
    if 40 <= t < 60:
        return random.random() < 0.5, 0.05
    return True, 0.05


class Breaker:
    def __init__(self):
        self.failures, self.opened_at, self.state = 0, None, "closed"

    def call(self, t):
        if self.state == "open":
            if t - self.opened_at < OPEN_FOR:
                return False, 0.0, False  # rejected at once, the dependency never sees it
            self.state = "half-open"
        ok, waited = dependency(t)
        if ok:
            self.failures, self.state = 0, "closed"
        else:
            self.failures += 1
            if self.state == "half-open" or self.failures >= THRESHOLD:
                self.state, self.opened_at = "open", t
        return ok, waited, True


def run(use_breaker):
    random.seed(1)
    b = Breaker()
    stats = {name: {"ok": 0, "sent": 0, "waited": 0.0, "reached": 0} for name, *_ in PHASES}
    for i in range(800):
        t = i / 10
        phase = next(name for name, start, end in PHASES if start <= t < end)
        ok, waited, reached = b.call(t) if use_breaker else (*dependency(t), True)
        s = stats[phase]
        s["sent"] += 1
        s["ok"] += ok
        s["waited"] += waited
        s["reached"] += reached
    return stats


for label, use in (("no breaker", False), ("breaker", True)):
    print(f"\n{label}")
    print(f"  {'phase':<14}{'success':>9}{'calls reaching dependency':>28}{'caller-seconds waiting':>25}")
    for name, s in run(use).items():
        print(f"  {name:<14}{s['ok'] / s['sent']:>9.0%}{s['reached']:>28}{s['waited']:>25.1f}")
