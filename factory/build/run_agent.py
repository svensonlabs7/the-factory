# /// script
# requires-python = "==3.12.*"
# dependencies = ["openhands-sdk==1.54.0", "openhands-workspace==1.54.0"]
# ///
"""Run one factory task with Claude Code inside an OpenHands Docker sandbox.

Usage: run_agent.py <workdir> <prompt> <timeout-seconds>

The sandbox sees only <workdir> and holds no GitHub credentials, so the caller
publishes the branch. The only secret it receives is CLAUDE_CODE_OAUTH_TOKEN,
which bills to the Claude plan.
"""
import sys

from openhands.sdk import Conversation
from openhands.sdk.agent import ACPAgent
from openhands.workspace import DockerWorkspace

# Pinned by digest. The tag is 1.54.0-python, which must match the SDK versions above.
SERVER_IMAGE = "ghcr.io/openhands/agent-server@sha256:082368832a7e48087b64da38c7b2cf2442dd7621fde69f8d06ed52283ff136f8"
SANDBOX_DIR = "/workspace/project"

# The Docker VM mounts only the home directory, so <workdir> must live under it.
workdir, prompt, timeout = sys.argv[1:]
# The caller passes a timeout shorter than its own kill limit, so a stuck agent ends here and the container is removed.
agent = ACPAgent(acp_command=["claude-agent-acp"], acp_prompt_timeout=float(timeout))
with DockerWorkspace(
    server_image=SERVER_IMAGE,
    platform="linux/arm64",
    working_dir=SANDBOX_DIR,
    volumes=[f"{workdir}:{SANDBOX_DIR}"],
    forward_env=["CLAUDE_CODE_OAUTH_TOKEN"],
) as workspace:
    conversation = Conversation(agent=agent, workspace=workspace)
    conversation.send_message(prompt)
    conversation.run()
