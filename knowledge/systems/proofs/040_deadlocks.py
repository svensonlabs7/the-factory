"""Deadlocks. Every wait has a timeout here, so the experiment cannot hang.
A. Two threads take two locks in opposite orders -> each holds one and waits for the other. Fix: one global order.
B. The adapter's real HEARTBEAT_LOCK is a non-reentrant Lock: code that already holds it and calls _set_heartbeat
   would block forever (shown in a daemon thread, which is then abandoned).
C. A single-worker executor (like RUN_EXECUTOR, max_workers=1) whose task submits another task and waits for it."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from test_adapter import adapter  # noqa: F401  (fixture)


def two_locks(ordered):
    a, b = threading.Lock(), threading.Lock()
    results = []

    def worker(first, second, name):
        with first:
            time.sleep(0.1)
            got = second.acquire(timeout=1)
            results.append((name, got))
            if got:
                second.release()
    order = [(a, b), (a, b)] if ordered else [(a, b), (b, a)]
    ts = [threading.Thread(target=worker, args=(*order[i], f"t{i}")) for i in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return results


def test_lock_order():
    print(f"\nA  opposite order: {two_locks(False)}   (False = gave up after 1 s: deadlocked)")
    print(f"A  same order:     {two_locks(True)}")


def test_heartbeat_lock_not_reentrant(adapter):
    module, root, client = adapter
    done = threading.Event()

    def nested():
        with module.HEARTBEAT_LOCK:
            module._set_heartbeat(pipeline_status="nested")  # tries to take the same lock again
        done.set()
    threading.Thread(target=nested, daemon=True).start()
    finished = done.wait(1)
    print(f"B  holding HEARTBEAT_LOCK, then calling _set_heartbeat: finished = {finished} (blocked on itself)")
    print(f"B  lock type: {type(module.HEARTBEAT_LOCK).__name__}; an RLock would let the same thread re-enter")


def test_single_worker_executor():
    ex = ThreadPoolExecutor(max_workers=1)

    def outer():
        inner = ex.submit(lambda: "inner done")
        try:
            return inner.result(timeout=1)
        except FutureTimeout:
            return "outer waited 1 s for inner; inner can never start: the only worker is outer"
    print(f"C  {ex.submit(outer).result()}")
    ex.shutdown(wait=True)
