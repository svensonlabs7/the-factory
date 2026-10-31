"""Event-driven architecture.
A. Choreography by event notification: each step reacts to the previous step's event. One subscription misspelled,
   and the flow stops with no error anywhere. Orchestration (one function calling the steps) fails loudly.
B. The dual write in the real adapter: a run's state (meta.json) and its event log (actions.jsonl) are two separate
   writes, and the event write is best-effort. When the event log cannot be written, /status reports a completed
   run whose events say otherwise. (tests/test_adapter.py's fixture; only the .actions.jsonl appends fail.)"""
from collections import defaultdict

from test_adapter import adapter, trigger, wait_done  # noqa: F401  (fixture)


def test_choreography_vs_orchestration():
    subscribers, done = defaultdict(list), []

    def on(event):
        return lambda fn: subscribers[event].append(fn)

    def emit(event):
        for fn in subscribers[event]:
            fn()

    @on("built")
    def push(): done.append("pushed"); emit("pushed")

    @on("pushd")  # the typo: nobody ever reacts to "pushed"
    def open_pr(): done.append("pr opened"); emit("pr_opened")

    done.append("built")
    emit("built")
    print(f"\nA  choreography: steps done {done}; errors raised: none; nothing says the flow stopped")

    steps = {"build": lambda: "built", "push": lambda: "pushed"}
    try:
        [steps[s]() for s in ("build", "push", "open_pr")]
    except KeyError as exc:
        print(f"A  orchestration: KeyError {exc} at the missing step")


def test_dual_write(adapter, monkeypatch):
    module, root, client = adapter
    real = module._append_jsonl

    def flaky(path, entry):
        if path.name.endswith(".actions.jsonl") and entry["event"] not in ("queued",):
            raise OSError(28, "No space left on device")
        return real(path, entry)

    monkeypatch.setattr(module, "_append_jsonl", flaky)
    run_id = trigger(client).json()["run_id"]
    status = wait_done(client, run_id)
    print(f"B  /status: status {status['status']!r}; its events: {status['actions']}")
