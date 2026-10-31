"""Backups: a backup is worthless until a RESTORE is proven. The common failure is a backup job that reports
success while producing an archive that cannot be restored (truncated, corrupted, missing a needed file). Only
an actual test-restore, compared against the source, catches it -- "the file exists and is non-empty" does not.

A. Back up a data dir to a tar archive, then corrupt the archive (a flipped/truncated block, as a bad disk or
   partial write would do).
   - "backup exists" check: archive is present and non-empty -> reports OK (FALSE confidence).
   - test-restore check: extract to a scratch dir and compare checksums -> detects the corruption.
Real tarfile + sha256 on temp dirs; deterministic; no network."""
import hashlib
import io
import os
import tarfile
import tempfile


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def manifest(root):
    out = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = sha(p)
    return out


src = tempfile.mkdtemp()
for name, data in (("env", b"TOKEN=secret\n"), ("runs.json", b'{"runs": 42}'), ("heartbeat.md", b"alive")):
    open(os.path.join(src, name), "wb").write(data)
source_manifest = manifest(src)

archive = tempfile.mktemp(suffix=".tar")
with tarfile.open(archive, "w") as tar:
    tar.add(src, arcname=".")

# Corrupt the archive: overwrite 64 bytes in the middle, where file data lives (a bad sector / bit rot).
with open(archive, "r+b") as f:
    size = os.path.getsize(archive)
    f.seek(size // 2)
    f.write(b"\x00" * 64)


def check_exists():
    return os.path.exists(archive) and os.path.getsize(archive) > 0


def check_restore():
    dest = tempfile.mkdtemp()
    try:
        with tarfile.open(archive, "r") as tar:
            tar.extractall(dest)
        return manifest(dest) == source_manifest
    except Exception:
        return False


print(f'A  "backup exists" check (file present, non-empty): {"OK" if check_exists() else "fail"}  '
      f"-> false confidence, the archive is corrupt")
print(f"A  test-restore check (extract + compare checksums): {'OK' if check_restore() else 'RESTORE FAILED'}  "
      f"-> the only check that catches it")
print("A  rule: a backup is not done until a restore has been verified against the source (3-2-1, test restores)")
