"""Garbage collection in CPython 3.11.
A. Reference cycles: refcounting alone cannot free them. With the cycle collector disabled, 2,000 cycles holding
   50 KB each stay in memory after the last reference is dropped; gc.collect() frees them.
B. A full collection is stop-the-world work proportional to the tracked container objects: pause vs heap size.
C. The adapter's own heap (real module via the test fixture): how long a full collection takes there."""
import gc
import time
import tracemalloc

from test_adapter import adapter  # noqa: F401  (fixture)


class Node:
    def __init__(self):
        self.blob = bytearray(50_000)
        self.other = None


def test_cycles_need_the_collector():
    gc.collect()
    gc.disable()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    for _ in range(2000):
        a, b = Node(), Node()
        a.other, b.other = b, a   # a cycle; the names are rebound on the next loop, so nothing references it
    held = tracemalloc.get_traced_memory()[0] - base
    freed = gc.collect()
    after = tracemalloc.get_traced_memory()[0] - base
    tracemalloc.stop()
    gc.enable()
    print(f"\nA  gc disabled, 2,000 dropped cycles still held: {held / 2**20:.0f} MiB; gc.collect() found {freed} objects; now {after / 2**20:.1f} MiB")


def test_full_collection_pause():
    for n in (100_000, 1_000_000, 3_000_000):
        heap = [{"i": i} for i in range(n)]
        gc.collect()
        t = time.perf_counter()
        gc.collect()
        ms = (time.perf_counter() - t) * 1e3
        print(f"B  {n:>9,} tracked dicts alive: full gc.collect() pause {ms:7.1f} ms")
        del heap
    gc.collect()


def test_adapter_heap_pause(adapter):
    module, root, client = adapter
    for _ in range(50):
        client.get("/command/data")
    gc.collect()
    t = time.perf_counter()
    gc.collect()
    ms = (time.perf_counter() - t) * 1e3
    print(f"C  process holding the adapter (+FastAPI, httpx, pytest): {len(gc.get_objects()):,} tracked objects, full collection {ms:.1f} ms; thresholds {gc.get_threshold()}")
