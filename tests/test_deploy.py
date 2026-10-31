import pathlib
import plistlib
import subprocess

PLIST = pathlib.Path(__file__).resolve().parents[1] / "factory/intake/com.svenson.factory-intake.plist"


def test_the_service_listens_on_localhost_only():
    args = plistlib.loads(PLIST.read_bytes())["ProgramArguments"]
    assert args[args.index("--host") + 1] == "127.0.0.1"


def test_the_beacon_runs_the_script_every_ten_minutes():
    beacon = plistlib.loads((PLIST.parent / "com.svenson.factory-beacon.plist").read_bytes())
    assert beacon["ProgramArguments"][0].endswith("/factory/intake/beacon.sh")
    assert beacon["StartInterval"] == 600


def test_install_check_reports_missing_drift_and_ok_without_touching_launchd(tmp_path):
    repo = PLIST.parents[2]
    check = lambda: subprocess.run(["bash", str(repo / "infra/install.sh"), "--check"], env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
                                   capture_output=True, text=True)
    first = check()
    assert first.returncode == 1 and first.stdout.count("MISSING") == 4
    pairs = [("infra/cloudflare-tunnel/config.yml", ".cloudflared/config.yml")] + [
        (src, f"Library/LaunchAgents/{pathlib.Path(src).name}") for src in (
            "infra/cloudflare-tunnel/com.cloudflare.cloudflared.plist", "factory/intake/com.svenson.factory-intake.plist",
            "factory/intake/com.svenson.factory-beacon.plist")]
    for src, dst in pairs:
        (tmp_path / dst).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / dst).write_bytes((repo / src).read_bytes())
    assert check().returncode == 0
    (tmp_path / ".cloudflared/config.yml").write_text("changed by hand\n")
    drift = check()
    assert drift.returncode == 1 and f"DRIFT  {tmp_path}/.cloudflared/config.yml" in drift.stdout
