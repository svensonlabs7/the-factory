import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAUDE_MD = (ROOT / "CLAUDE.md").read_text()
MAPPING = (ROOT / "vendor/pstack/CLAUDE-CODE.md").read_text()

# Cursor-only terms found in the vendored pstack skills. Each needs a Claude Code equivalent or a skip.
CURSOR_ONLY = [
    "cursor-team-kit", "deslop", "control-cli", "control-ui", "create-skill", "Bugbot", "grok-", "cloud agent",
    "generalPurpose", "Origin", "Graphite", "AskQuestion", ".cursor", ".mdc", "alwaysApply", "/setup-pstack",
    "/loop", "Plan Mode",
]


@pytest.mark.parametrize("term", CURSOR_ONLY)
def test_cursor_only_term_is_mapped(term):
    assert term in MAPPING


def test_autopilot_full_is_a_playbook_not_a_command():
    assert "`/autopilot-full`" not in CLAUDE_MD + MAPPING


def test_claude_md_points_to_the_mapping():
    assert "vendor/pstack/CLAUDE-CODE.md" in CLAUDE_MD
