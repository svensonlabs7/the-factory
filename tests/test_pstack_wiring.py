import pathlib

import pytest

CLAUDE_MD = (pathlib.Path(__file__).resolve().parents[1] / "CLAUDE.md").read_text()

# Cursor-only terms found in the vendored pstack skills. Each needs a Claude Code equivalent or a skip.
CURSOR_ONLY = [
    "cursor-team-kit", "deslop", "control-cli", "control-ui", "create-skill", "Bugbot", "grok-", "cloud agent",
    "generalPurpose", "Origin", "Graphite", "AskQuestion", ".cursor", ".mdc", "alwaysApply", "/setup-pstack",
    "/loop", "Plan Mode",
]


@pytest.mark.parametrize("term", CURSOR_ONLY)
def test_cursor_only_term_is_mapped(term):
    assert term in CLAUDE_MD


def test_autopilot_full_is_a_playbook_not_a_command():
    assert "`/autopilot-full`" not in CLAUDE_MD
