# /// script
# requires-python = "==3.12.*"
# dependencies = ["openhands-sdk==1.54.0", "openhands-workspace==1.54.0"]
# ///
import time; t = time.perf_counter()
from openhands.sdk import Conversation; from openhands.sdk.agent import ACPAgent; from openhands.workspace import DockerWorkspace
print(f"imports {time.perf_counter() - t:.2f} s")
