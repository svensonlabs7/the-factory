"""Retries: when they help, how they hurt, and the fixes.
A. A flaky dependency (20% transient failures): retries raise success from ~80% to ~99%.
B. A dead dependency behind 3 layers that each retry: load multiplies per layer. Fix: retry at one layer.
C. Even one retrying layer triples load on a dead dependency. Fix: a retry budget (token bucket, ~10%).
D. Retrying a permanent error only wastes attempts. Fix: retry transient errors only."""
import random

random.seed(7)
calls = {"db": 0}


class Transient(Exception): pass
class Permanent(Exception): pass


def db(fail_rate):
    calls["db"] += 1
    if random.random() < fail_rate:
        raise Transient()
    return "ok"


def with_retries(fn, attempts, retry_on=(Transient,)):
    for i in range(attempts):
        try:
            return fn()
        except retry_on:
            if i == attempts - 1:
                raise


def success_rate(fn, n=10000):
    ok = 0
    for _ in range(n):
        try:
            fn()
            ok += 1
        except Exception:
            pass
    return ok / n


print(f"A  flaky db, no retry:      success {success_rate(lambda: db(0.2)):.1%}")
print(f"A  flaky db, 3 attempts:    success {success_rate(lambda: with_retries(lambda: db(0.2), 3)):.1%}")


def stack(retry_layers, attempts=3):
    """User -> api -> service -> db. Each layer in retry_layers retries its call below."""
    def wrap(fn, layer):
        return (lambda: with_retries(fn, attempts, retry_on=(Exception,))) if layer in retry_layers else fn
    svc = wrap(lambda: db(1.0), "service")
    api = wrap(svc, "api")
    return wrap(api, "user")


for layers in (("user", "api", "service"), ("user",)):
    calls["db"] = 0
    success_rate(stack(layers), n=100)
    print(f"B  dead db, retries at {'+'.join(layers):<19} db calls per request: {calls['db'] / 100:.0f}")


class Budget:
    """Token bucket: each success earns 0.1 tokens, each retry spends 1, so retries stay near 10% of requests."""
    def __init__(self, cap=10):
        self.tokens = self.cap = cap

    def call(self, fn, attempts=3):
        for i in range(attempts):
            try:
                result = fn()
                self.tokens = min(self.cap, self.tokens + 0.1)
                return result
            except Transient:
                if i == attempts - 1 or self.tokens < 1:
                    raise
                self.tokens -= 1


calls["db"] = 0
success_rate(lambda: with_retries(lambda: db(1.0), 3), n=1000)
print(f"C  dead db, 3 attempts, no budget: {calls['db'] / 1000:.2f} db calls per request")
calls["db"] = 0
b = Budget()
success_rate(lambda: b.call(lambda: db(1.0)), n=1000)
print(f"C  dead db, 3 attempts, budget:    {calls['db'] / 1000:.2f} db calls per request")


def bad_request():
    calls["db"] += 1
    raise Permanent("400: invalid branch name")


for label, retry_on in (("retry everything", (Exception,)), ("retry transient", (Transient,))):
    calls["db"] = 0
    success_rate(lambda: with_retries(bad_request, 3, retry_on=retry_on), n=100)
    print(f"D  permanent error, {label:<16} calls per request: {calls['db'] / 100:.0f}")
