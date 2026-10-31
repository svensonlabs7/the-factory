"""Review 50: is the bound port really a single-instance lock? uvicorn imports the app module (which runs _recover)
before it binds. Scratch FACTORY_ROOT and a scratch port, so the live adapter is untouched."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO, PORT = Path(sys.argv[1]), 18750
ROOT = Path(tempfile.mkdtemp())
shutil.copy(REPO / "HEARTBEAT.template.md", ROOT / "HEARTBEAT.template.md")
ENV = {**os.environ, "FACTORY_ROOT": str(ROOT), "FACTORY_WEBHOOK_SECRET": "scratch"}
CMD = ["uv", "run", "-q", "--python", "3.11", "--with", "fastapi", "--with", "uvicorn", "--",
       "uvicorn", "factory.intake.webhook_adapter:app", "--port", str(PORT)]

first = subprocess.Popen(CMD, cwd=REPO, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(200):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=0.5)
        break
    except Exception:
        time.sleep(0.05)
meta = ROOT / ".factory-logs" / "live1.meta.json"
meta.write_text(json.dumps({"run_id": "live1", "status": "running", "queued_at": time.time()}))  # the first instance's run in flight
second = subprocess.run(CMD, cwd=REPO, env=ENV, capture_output=True, text=True, timeout=60)
bind_error = next((line.strip() for line in second.stderr.splitlines() if "address already in use" in line.lower()), second.stderr.strip()[-120:])
after = json.loads(meta.read_text())
print(f"second instance on the same port: exit {second.returncode}, {bind_error!r}")
print(f"first instance's in-flight run after the failed start: status {after['status']!r}, error {after.get('error')!r}")
first.terminate()
first.wait()
shutil.rmtree(ROOT)
