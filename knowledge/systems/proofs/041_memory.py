"""Memory leaks in a garbage-collected language = memory still reachable that nothing will ever free.
B. The adapter's real _pr_cache (fixture, gh stubbed): feed it 5,000 distinct PR URLs and measure with tracemalloc.
   It only inserts (merged/closed PRs are kept 'for good'), so it grows with every PR ever shown, for the process's life.
C. The same 5,000 keys through functools.lru_cache(maxsize=256): memory stays capped."""
import functools
import gc
import json
import tracemalloc

from test_adapter import adapter  # noqa: F401  (fixture)

ROLLUP = json.dumps({"state": "MERGED", "statusCheckRollup": [
    {"name": n, "conclusion": "SUCCESS", "status": "COMPLETED"} for n in ("lint", "secrets", "tests", "thermo-nuclear", "ponytail-review", "ux-laws")]})


def test_pr_cache_growth(adapter, monkeypatch):
    module, root, client = adapter
    monkeypatch.setattr(module, "_run", lambda *cmd, **kw: ROLLUP)
    module._pr_cache.clear()
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.take_snapshot()
    for i in range(5000):
        module._pr(f"https://github.com/svensonlabs7/the-factory/pull/{i}")
    gc.collect()
    after = tracemalloc.take_snapshot()
    grown = sum(s.size_diff for s in after.compare_to(before, "filename"))
    tracemalloc.stop()
    print(f"\nB  _pr_cache after 5,000 PRs: {len(module._pr_cache)} entries, +{grown / 1024:.0f} KiB "
          f"({grown / 5000:.0f} B per PR); entries ever removed: {5000 - len(module._pr_cache)}")
    per_pr = grown / 5000
    for runs_per_day in (3, 30):
        print(f"B  at {runs_per_day} PRs/day, without a restart: ~{per_pr * runs_per_day * 365 / 1024 / 1024:.1f} MiB/year")


def test_bounded_cache():
    @functools.lru_cache(maxsize=256)
    def pr(url):
        return json.loads(ROLLUP)
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.take_snapshot()
    for i in range(5000):
        pr(f"https://github.com/svensonlabs7/the-factory/pull/{i}")
    gc.collect()
    grown = sum(s.size_diff for s in tracemalloc.take_snapshot().compare_to(before, "filename"))
    tracemalloc.stop()
    print(f"C  lru_cache(maxsize=256) after 5,000 PRs: {pr.cache_info().currsize} entries, +{grown / 1024:.0f} KiB (capped)")
