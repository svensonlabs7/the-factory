# /// script
# requires-python = "==3.12.*"
# dependencies = ["openhands-sdk==1.54.0", "openhands-workspace==1.54.0"]
# ///
"""Run one factory task with Claude Code inside an OpenHands Docker sandbox.

Usage: run_agent.py <workdir> <prompt> <timeout-seconds>

The sandbox sees only <workdir> and holds no GitHub credentials, so the caller
publishes the branch. The only secret it receives is CLAUDE_CODE_OAUTH_TOKEN,
which bills to the Claude plan. Its network reaches only the hosts in egress/allow,
through a proxy, so that token cannot be sent anywhere else (egress.sh).
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

from openhands.sdk import Conversation
from openhands.sdk.agent import ACPAgent
from openhands.workspace import DockerWorkspace

# Pinned by digest. The tag is 1.54.0-python, which must match the SDK versions above.
SERVER_IMAGE = "ghcr.io/openhands/agent-server@sha256:082368832a7e48087b64da38c7b2cf2442dd7621fde69f8d06ed52283ff136f8"
SANDBOX_DIR = "/workspace/project"
PROXY = "http://172.30.0.2:8888"  # factory-egress, set up by egress.sh

# The caller's round timeout SIGTERMs this process first. Exit normally so the `with DockerWorkspace` block
# below still runs its cleanup and removes the container, instead of dying mid-conversation and leaking it.
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

# The Docker VM mounts only the home directory, so <workdir> must live under it.
workdir, prompt, timeout = sys.argv[1:]
# Fail closed: no run starts unless egress.sh has locked the sandbox network down and proven it.
subprocess.run([str(Path(__file__).with_name("egress.sh"))], check=True)
# Set here, not by the caller, so only the container uses the proxy (forward_env copies these names in).
os.environ.update(HTTPS_PROXY=PROXY, HTTP_PROXY=PROXY, NO_PROXY="localhost,127.0.0.1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
# The caller passes a timeout shorter than its own kill limit, so a stuck agent ends here and the container is removed.
agent = ACPAgent(acp_command=["claude-agent-acp"], acp_prompt_timeout=float(timeout))
with DockerWorkspace(
    server_image=SERVER_IMAGE,
    platform="linux/arm64",
    working_dir=SANDBOX_DIR,
    volumes=[f"{workdir}:{SANDBOX_DIR}"],
    network="factory-sandbox",
    forward_env=["CLAUDE_CODE_OAUTH_TOKEN", "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"],
) as workspace:
    conversation = Conversation(agent=agent, workspace=workspace)
    conversation.send_message(prompt)
    conversation.run()
