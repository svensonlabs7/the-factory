"""Semantic versioning and Hyrum's law in the factory.
A. (run separately with uv) Starlette's 0.x -> 1.x major bump removed `on_startup`; the adapter's `lifespan` survives it.
B. The adapter's _gate_results depends on gh's human-readable error text ("no required checks reported on the ...
   branch"), which no version number promises. Same gh behaviour, reworded message: the wait turns into a failure.
   Real _gate_results via tests/test_adapter.py's fixture; only `_run` is replaced, to play gh."""
import json

from test_adapter import adapter  # noqa: F401  (fixture)


def gh(module, message, monkeypatch):
    calls = {"checks": 0}

    def fake_run(*cmd, cwd=None):
        if cmd[1:3] == ("pr", "view"):
            return "abc123"
        calls["checks"] += 1
        if calls["checks"] < 3:  # GitHub has not registered the checks yet, as just after a push
            raise RuntimeError(f"gh pr checks: {message}")
        return json.dumps([{"name": "tests", "bucket": "pass"}])

    monkeypatch.setattr(module, "_run", fake_run)
    try:
        return f"waited, then {module._gate_results('https://example.invalid/pull/1', 'abc123')}"
    except RuntimeError as exc:
        return f"RuntimeError after {calls['checks']} poll(s): {exc}"


def test_message_contract(adapter, monkeypatch):
    module, root, client = adapter
    current = gh(module, "no required checks reported on the 'factory/x' branch", monkeypatch)
    reworded = gh(module, "no required status checks found for 'factory/x'", monkeypatch)
    print(f"\nB  gh 2.101.0 wording: {current}")
    print(f"B  reworded by a gh release: {reworded}")
