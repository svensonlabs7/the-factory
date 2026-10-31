"""CI/CD.
A. Semantic conflict: two branches each pass CI against the base they started from and merge with no textual
   conflict, but main breaks. Requiring the branch to be up to date (re-test the merge with current main) catches it.
B. Unpinned dependencies: the same `fastapi` requirement resolves to different versions depending on the day it is
   installed, so CI and production can run code nobody tested together. A pin resolves the same every time."""
import subprocess
import sys
import tempfile
from pathlib import Path


def sh(*cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def ci(repo):  # the "test suite": import the app and every module that calls the library
    r = sh(sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import app; [__import__(m) for m in ('report',) if __import__('os').path.exists(m + '.py')]; app.main()", cwd=repo, check=False)
    return "green" if r.returncode == 0 else "red (" + r.stderr.strip().splitlines()[-1] + ")"


def commit(repo, msg, files):
    for name, text in files.items():
        (repo / name).write_text(text)
    sh("git", "add", "-A", cwd=repo)
    sh("git", "commit", "-qm", msg, cwd=repo)


def semantic_conflict():
    repo = Path(tempfile.mkdtemp())
    sh("git", "init", "-qb", "main", cwd=repo)
    sh("git", "config", "user.email", "x@example.com", cwd=repo)
    sh("git", "config", "user.name", "x", cwd=repo)
    commit(repo, "base", {"lib.py": "def fetch(u):\n    return u\n", "app.py": "import lib\ndef main():\n    lib.fetch('a')\n"})
    sh("git", "branch", "a", cwd=repo)
    sh("git", "branch", "b", cwd=repo)
    sh("git", "checkout", "-q", "a", cwd=repo)
    commit(repo, "rename fetch to get", {"lib.py": "def get(u):\n    return u\n", "app.py": "import lib\ndef main():\n    lib.get('a')\n"})
    a_ci = ci(repo)
    sh("git", "checkout", "-q", "b", cwd=repo)
    commit(repo, "add report", {"report.py": "import lib\nlib.fetch('r')\n"})
    b_ci = ci(repo)
    print(f"A  CI on each branch against the old base: a {a_ci}, b {b_ci}")
    sh("git", "checkout", "-q", "main", cwd=repo)
    sh("git", "merge", "-q", "--no-ff", "-m", "merge a", "a", cwd=repo)
    print(f"A  main after merging a: {ci(repo)}")
    # Not strict: b's green result is from before a landed, so it merges on that stale result.
    merged = sh("git", "merge", "-q", "--no-ff", "-m", "merge b", "b", cwd=repo, check=False)
    print(f"A  not strict: merge b on its stale green -> textual conflict: {merged.returncode != 0}; main is now {ci(repo)}")
    sh("git", "reset", "-q", "--hard", "HEAD~1", cwd=repo)
    # Strict: b must be brought up to date with main and re-tested before it may merge.
    sh("git", "checkout", "-q", "b", cwd=repo)
    sh("git", "merge", "-q", "-m", "update b from main", "main", cwd=repo)
    print(f"A  strict: b updated with main and re-tested -> {ci(repo)}, merge blocked; main stays {ci_main(repo)}")


def ci_main(repo):
    sh("git", "checkout", "-q", "main", cwd=repo)
    return ci(repo)


def drift():
    for spec in ("fastapi", "fastapi==0.110.0"):
        found = []
        for date in ("2025-01-01", "2025-09-01", "2026-10-18"):
            r = subprocess.run(["uv", "pip", "compile", "-", "--python-version", "3.11", "--exclude-newer", date,
                                "--quiet", "--no-header", "--no-annotate"], input=spec, capture_output=True, text=True, check=True)
            pins = dict(line.split("==") for line in r.stdout.split() if line.startswith(("fastapi==", "starlette==")))
            found.append(f"{date}: fastapi {pins['fastapi']} starlette {pins['starlette']}")
        print(f"B  requirement {spec!r} installed on\n     " + "\n     ".join(found))


semantic_conflict()
drift()
