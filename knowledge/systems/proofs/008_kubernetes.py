"""Kubernetes' core idea is the RECONCILIATION LOOP: you declare desired state (e.g. 3 replicas of a pod) and
a controller continuously observes actual state and acts to close the gap. That is what gives self-healing
(a crashed pod is recreated) and declarative scaling (change the number, the controller converges) -- as
opposed to an imperative "start N processes" that does nothing when one later dies.

A. Self-healing: a Deployment wants 3 replicas. Pods crash over time. The reconciler recreates them each tick,
   so the running count returns to 3. A one-shot launcher starts 3 and never recovers -> count decays.
B. Declarative scale: change desired to 5, then to 2; the reconciler converges to each without manual add/remove.
Deterministic seed; a virtual clock; no cluster."""
import random

random.seed(3)
TICKS = 12


class Reconciler:
    """A Deployment controller: each tick, make the running set match `desired` replicas."""
    def __init__(self, desired):
        self.desired, self.pods, self._next = desired, set(), 0

    def crash_random(self, p=0.3):
        for pod in list(self.pods):
            if random.random() < p:
                self.pods.discard(pod)          # a pod dies (OOM, node loss, bug)

    def reconcile(self):
        while len(self.pods) < self.desired:    # observe gap, create to close it
            self.pods.add(self._next); self._next += 1
        while len(self.pods) > self.desired:    # scale in
            self.pods.discard(max(self.pods))


class OneShot:
    """Imperative: start `n` once, never reconcile."""
    def __init__(self, n):
        self.pods = set(range(n))

    def crash_random(self, p=0.3):
        for pod in list(self.pods):
            if random.random() < p:
                self.pods.discard(pod)

    def reconcile(self):
        pass                                     # nothing drives it back to desired


print("A  self-healing under random crashes (desired=3):")
k8s, imp = Reconciler(3), OneShot(3)
for t in range(TICKS):
    k8s.crash_random(); k8s.reconcile()
    imp.crash_random(); imp.reconcile()
print(f"   reconciler: running={len(k8s.pods)} (back to desired), total pods ever created={k8s._next}")
print(f"   one-shot  : running={len(imp.pods)} (decayed, no recovery)")

print("B  declarative scale (reconciler), no manual add/remove:")
dep = Reconciler(3); dep.reconcile()
for target in (5, 2):
    dep.desired = target; dep.reconcile()
    print(f"   desired={target} -> running={len(dep.pods)}")
