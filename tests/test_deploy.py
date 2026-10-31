import pathlib
import plistlib

PLIST = pathlib.Path(__file__).resolve().parents[1] / "factory/intake/com.svenson.factory-intake.plist"


def test_the_service_listens_on_localhost_only():
    args = plistlib.loads(PLIST.read_bytes())["ProgramArguments"]
    assert args[args.index("--host") + 1] == "127.0.0.1"


def test_the_beacon_runs_the_script_every_ten_minutes():
    beacon = plistlib.loads((PLIST.parent / "com.svenson.factory-beacon.plist").read_bytes())
    assert beacon["ProgramArguments"][0].endswith("/factory/intake/beacon.sh")
    assert beacon["StartInterval"] == 600
