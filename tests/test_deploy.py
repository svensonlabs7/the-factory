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


FAKE_LAUNCHCTL = """#!/bin/sh
# Like launchctl: print and kickstart fail for a service that is not loaded; bootstrap loads one. bootout of a loaded
# service returns at once but leaves it unloading for two more prints, and bootstrap fails (5) until then.
log="$HOME/launchctl.log"; loaded="$HOME/loaded"; touch "$loaded"
echo "$*" >> "$log"
label=${2##*/}; [ "$1" = kickstart ] && label=${3##*/}; [ "$1" = bootstrap ] && label=$(basename "$3" .plist)
unloading="$HOME/unloading-$label"
case "$1" in
  print) n=$(cat "$unloading" 2>/dev/null || echo 0)
         if [ "$n" -gt 0 ]; then echo $((n - 1)) > "$unloading"; exit 0; fi
         grep -qx "$label" "$loaded" || exit 113 ;;
  kickstart) grep -qx "$label" "$loaded" || exit 113 ;;
  bootout) grep -qx "$label" "$loaded" || exit 3
           grep -vx "$label" "$loaded" > "$loaded.new"; mv "$loaded.new" "$loaded"; echo 2 > "$unloading" ;;
  bootstrap) [ "$(cat "$unloading" 2>/dev/null || echo 0)" -gt 0 ] && exit 5
             echo "$label" >> "$loaded" ;;
esac
"""


def test_install_on_a_fresh_host_loads_every_agent_and_a_second_run_does_nothing(tmp_path):
    repo, bin_dir = PLIST.parents[2], tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "launchctl").write_text(FAKE_LAUNCHCTL)
    (bin_dir / "launchctl").chmod(0o755)
    run = lambda: subprocess.run(["bash", str(repo / "infra/install.sh")], capture_output=True, text=True,
                                 env={"HOME": str(tmp_path), "PATH": f"{bin_dir}:/usr/bin:/bin"})
    first = run()
    assert first.returncode == 0, first.stderr
    log = (tmp_path / "launchctl.log").read_text()
    assert log.count("bootstrap ") == 3 and "kickstart" not in log
    (tmp_path / "launchctl.log").unlink()
    second = run()
    assert second.returncode == 0 and second.stdout.count("ok  ") == 4 and not (tmp_path / "launchctl.log").exists()


def test_restart_refuses_while_a_run_is_in_flight(tmp_path):
    repo = PLIST.parents[2]
    (tmp_path / "curl").write_text('#!/bin/sh\n[ "$PENDING" = down ] && exit 7\necho "{\\"status\\": \\"ok\\", \\"pending\\": $PENDING}"\n')
    (tmp_path / "launchctl").write_text('#!/bin/sh\necho "$*" >> "$LOG"\n')
    for name in ("curl", "launchctl"):
        (tmp_path / name).chmod(0o755)
    run = lambda pending, *args: subprocess.run(["bash", str(repo / "factory/intake/restart.sh"), *args], capture_output=True, text=True,
                                                env={"PATH": f"{tmp_path}:/usr/bin:/bin", "PENDING": pending, "LOG": str(tmp_path / "log")})
    busy = run("1")
    assert busy.returncode == 1 and "in flight" in busy.stderr and not (tmp_path / "log").exists()
    assert run("0").returncode == 0 and "kickstart -k" in (tmp_path / "log").read_text()
    assert run("2", "--force").returncode == 0
    down = run("down")
    assert down.returncode == 1 and "not answering" in down.stderr
    unknown = run("null")
    assert unknown.returncode == 1 and "could not count" in unknown.stderr


def test_the_adapter_runs_from_the_lock():
    args = plistlib.loads(PLIST.read_bytes())["ProgramArguments"]
    assert args[1:4] == ["run", "--frozen", "--"] and "--with" not in args
    assert (PLIST.parents[2] / "uv.lock").exists() and (PLIST.parents[2] / "factory/build/run_agent.py.lock").exists()


def test_restart_force_brings_back_an_adapter_that_was_down(tmp_path):
    repo = PLIST.parents[2]
    (tmp_path / "curl").write_text('#!/bin/sh\n[ -e "$LOG" ] || exit 7\necho ok\n')  # answers only after the kickstart
    (tmp_path / "launchctl").write_text('#!/bin/sh\necho "$*" >> "$LOG"\n')
    for name in ("curl", "launchctl"):
        (tmp_path / name).chmod(0o755)
    result = subprocess.run(["bash", str(repo / "factory/intake/restart.sh"), "--force"], capture_output=True, text=True,
                            env={"PATH": f"{tmp_path}:/usr/bin:/bin", "LOG": str(tmp_path / "log")})
    assert result.returncode == 0 and "the adapter is back" in result.stdout


def test_reinstalling_a_changed_agent_waits_for_launchd_to_unload_it(tmp_path):
    repo, bin_dir = PLIST.parents[2], tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "launchctl").write_text(FAKE_LAUNCHCTL)
    (bin_dir / "launchctl").chmod(0o755)
    run = lambda: subprocess.run(["bash", str(repo / "infra/install.sh")], capture_output=True, text=True,
                                 env={"HOME": str(tmp_path), "PATH": f"{bin_dir}:/usr/bin:/bin"})
    assert run().returncode == 0
    (tmp_path / "Library/LaunchAgents/com.svenson.factory-intake.plist").write_text("changed\n")
    second = run()
    assert second.returncode == 0, second.stderr
    assert "installed and reloaded com.svenson.factory-intake" in second.stdout
    reload = (tmp_path / "launchctl.log").read_text().split("bootout gui/")[-1].splitlines()
    assert sum(line.startswith("print ") for line in reload) == 3  # two "still unloading", then unloaded: the wait stops
