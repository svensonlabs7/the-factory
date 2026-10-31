"""Terraform tracks what it created in a STATE file and diffs desired-config against it to plan changes. The
state is the weak point: two applies against one shared state, with no lock, race on read-modify-write and lose
an update -- which is why Terraform locks the state (DynamoDB, a lock on the backend) for the duration of an apply.

Two concurrent applies, each adding a distinct resource to shared JSON state. A barrier forces both to read the
state before either writes, which is exactly the interleaving a lock prevents.
- no lock : both read {}, both write their own one-resource state -> last writer wins, the other resource is lost.
- lock    : the lock serializes the two applies -> both resources end up in state.
Real threads; deterministic via a barrier; no network."""
import json
import threading

STATE = {}  # the shared "terraform.tfstate"


def apply(resource, lock, barrier):
    with (lock if lock else _nullcx()):
        current = dict(STATE)              # read state
        barrier.wait(timeout=2)            # force the other apply to also read before anyone writes (no-lock case)
        current[resource] = {"created": True}
        STATE.clear()
        STATE.update(current)              # write state back


class _nullcx:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def run(use_lock):
    STATE.clear()
    lock = threading.Lock() if use_lock else None
    # With a lock, a 2-party barrier would deadlock (the 2nd apply blocks on the lock and never reaches wait),
    # so size the barrier to 1 under locking -- each apply proceeds alone, which is the point of the lock.
    barrier = threading.Barrier(1 if use_lock else 2)
    threads = [threading.Thread(target=apply, args=(r, lock, barrier)) for r in ("tunnel", "egress")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return dict(STATE)


for use_lock in (False, True):
    final = run(use_lock)
    label = "with state lock" if use_lock else "no lock       "
    ok = set(final) == {"tunnel", "egress"}
    print(f"{label}: final state has {sorted(final)}  -> {'both kept' if ok else 'an apply was LOST'}")
