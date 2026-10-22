"""Build caching: a cache is only as correct as its key. CPython's own bytecode cache (__pycache__/*.pyc, PEP 552).
A. Timestamp-keyed pyc (the default): the source changes but keeps its size and mtime (a restored or copied file
   with preserved timestamps) -> a fresh interpreter runs the stale cached bytecode.
B. Hash-keyed pyc (checked-hash, PEP 552): the same change is detected, because the key is the content."""
import os
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path


def run(d):
    return subprocess.run([sys.executable, "-c", "import mod; print(mod.VALUE)"], cwd=d, capture_output=True, text=True).stdout.strip()


for mode in (py_compile.PycInvalidationMode.TIMESTAMP, py_compile.PycInvalidationMode.CHECKED_HASH):
    d = Path(tempfile.mkdtemp())
    src = d / "mod.py"
    src.write_text("VALUE = 'v1'\n")
    stamp = (1_700_000_000, 1_700_000_000)
    os.utime(src, stamp)
    py_compile.compile(str(src), invalidation_mode=mode)       # the cached build output
    first = run(d)
    src.write_text("VALUE = 'v2'\n")                            # same size
    os.utime(src, stamp)                                        # same mtime, as a restored file keeps it
    print(f"{'A' if mode.name == 'TIMESTAMP' else 'B'}  key={mode.name:<12} source now says v2 -> program prints {run(d)!r} (first run {first!r})")
