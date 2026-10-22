"""Health checks.
A. The real adapter (fixture, fake agent): with gh broken (auth gone), /health still says ok, and a run builds,
   then fails when it tries to open the PR. A liveness check says nothing about whether the factory can deliver.
B. Simulation of AWS's warning: 10 servers behind a load balancer; 70% of requests need no shared dependency.
   When that dependency is down, deep health checks pull every server and nothing is served; shallow checks,
   or deep checks with fail-open, keep the 70% flowing."""
import stat

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)


def test_liveness_vs_delivery(adapter, tmp_path, monkeypatch):
    module, root, client = adapter
    broken_gh = tmp_path / "gh-logged-out"
    broken_gh.write_text("#!/bin/sh\necho 'To get started with GitHub CLI, please run:  gh auth login' >&2\nexit 4\n")
    broken_gh.chmod(broken_gh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(module, "GH_BIN", str(broken_gh))
    before = client.get("/health").json()
    run = wait_done(client, trigger(client).json()["run_id"])
    after = client.get("/health").json()
    events = [line.split('"event": "')[1].split('"')[0] for line in (root / ".factory-logs" / f"{run['run_id']}.actions.jsonl").read_text().splitlines()]
    print(f"\nA  /health before: {before}  after: {after}")
    print(f"A  run: status={run['status']!r} events={events}")
    print(f"A  error: ...{run.get('error', '')[-95:]!r}")


def test_deep_vs_shallow():
    servers, needs_dependency = 10, 0.3  # 70% of requests need no shared dependency
    print("\nB  shared dependency down; share of all requests served")
    for label, deep, fail_open in (("shallow liveness", False, False), ("deep, no fail-open", True, False), ("deep, fail-open", True, True)):
        healthy = 0 if deep else servers  # a deep check fails on every server at once
        in_rotation = servers if (healthy == 0 and fail_open) else healthy
        served = (1 - needs_dependency) if in_rotation else 0.0
        print(f"B  {label:<20} servers in rotation {in_rotation:>2}/10   served {served:.0%}")
