import pathlib
import plistlib

PLIST = pathlib.Path(__file__).resolve().parents[1] / "factory/intake/com.svenson.factory-intake.plist"


def test_the_service_listens_on_localhost_only():
    args = plistlib.loads(PLIST.read_bytes())["ProgramArguments"]
    assert args[args.index("--host") + 1] == "127.0.0.1"
