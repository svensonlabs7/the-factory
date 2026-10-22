"""API versioning, on the adapter's one external read API: GET /heartbeat, whose field names are the row names of
HEARTBEAT.template.md (real adapter via tests/test_adapter.py's fixture).
A. Contract today: every field the adapter writes has a row in the real template.
B. A breaking change: a row renamed in the template (as a fresh checkout copies it). A v1 client breaks.
C. The additive alternative: keep the old row, add the new one. The v1 client keeps working."""
import re
from pathlib import Path

from test_adapter import adapter  # noqa: F401  (fixture)

REPO = Path("/Users/labs/projects/the-factory")
ROW = r"\| \*\*(\w+)\*\* \|"


def v1_client(heartbeat: dict) -> str:  # what a watcher written against today's /heartbeat does
    return f"gate {heartbeat['qa_gate_status']}, pipeline {heartbeat['pipeline_status']}"


def test_contract_today():
    template = set(re.findall(ROW, (REPO / "HEARTBEAT.template.md").read_text()))
    code = REPO / "factory/intake/webhook_adapter.py"
    written = set(re.findall(r"\b(alive_at|last_run|open_incidents|pipeline_status|blocking_reason|build_status|qa_gate_status|intake_queue_depth|last_pr_merged|last_pr_blocked)=", code.read_text()))
    print(f"\nA  real template rows: {len(template)}; fields the adapter writes: {sorted(written)}; missing from the template: {sorted(written - template)}")


def run_once(module, root, client, heartbeat_text):
    (root / "HEARTBEAT.md").write_text(heartbeat_text)
    module._set_heartbeat(pipeline_status="completed", qa_gate_status="passed")
    beat = client.get("/heartbeat").json()
    try:
        return v1_client(beat)
    except KeyError as exc:
        return f"KeyError {exc}; fields now {sorted(k for k in beat if 'gate' in k)}"


def test_rename_vs_additive(adapter, caplog):
    module, root, client = adapter
    original = (root / "HEARTBEAT.md").read_text()
    print(f"B  today:              v1 client -> {run_once(module, root, client, original)}")
    renamed = original.replace("**qa_gate_status**", "**gate_status**")
    print(f"B  row renamed:        v1 client -> {run_once(module, root, client, renamed)}; adapter logged: {[r.getMessage() for r in caplog.records if 'no qa_gate_status' in r.getMessage()]}")
    additive = original + "| **gate_status** | — |\n"
    print(f"C  row added instead:  v1 client -> {run_once(module, root, client, additive)}")
