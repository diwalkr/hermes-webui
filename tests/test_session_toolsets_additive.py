"""Per-session toolset overrides are additive — they can never strip core toolsets.

Incident: sessions whose ``enabled_toolsets`` was set to MCP-only lists (by a router plugin,
and by users picking servers from the composer chip) were handed to the agent with no
terminal/file/delegation tools. The streaming worker used the override *instead of* the
profile list. Now ``api.config.merge_session_toolsets`` merges the profile's core toolsets
back in, and the streaming worker uses it as the single chokepoint.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from api.config import CORE_SESSION_TOOLSETS, merge_session_toolsets  # noqa: E402

PROFILE = ["clarify", "vision", "browser", "skills", "file", "delegation", "web",
           "memory", "terminal", "todo", "session_search", "cronjob", "codebase-memory"]


def test_no_override_returns_profile_unchanged():
    assert merge_session_toolsets(PROFILE, None) == PROFILE
    assert merge_session_toolsets(PROFILE, []) == PROFILE


def test_mcp_only_override_gets_core_toolsets_back():
    # The exact shape the router plugin wrote into session 9e9d5ef8a47d.
    merged = merge_session_toolsets(PROFILE, ["graft", "linear", "codebase-memory"])
    assert merged[:3] == ["graft", "linear", "codebase-memory"]  # caller's additions first
    for core in ("terminal", "file", "delegation", "skills", "todo", "clarify"):
        assert core in merged
    # non-core profile toolsets stay out — an override may still drop web/browser/memory
    assert "web" not in merged and "browser" not in merged


def test_override_already_containing_core_is_not_duplicated():
    merged = merge_session_toolsets(PROFILE, ["terminal", "linear", "terminal"])
    assert merged.count("terminal") == 1
    assert merged[0] == "terminal"


def test_core_not_granted_by_profile_is_not_invented():
    # A locked-down profile without terminal must stay without terminal.
    merged = merge_session_toolsets(["file", "web"], ["linear"])
    assert "terminal" not in merged
    assert merged == ["linear", "file"]


def test_non_string_entries_are_dropped():
    merged = merge_session_toolsets(PROFILE, ["linear", None, "", 3])
    assert merged[0] == "linear" and all(isinstance(x, str) and x for x in merged)


def test_streaming_worker_uses_merge_chokepoint():
    src = (REPO / "api" / "streaming.py").read_text(encoding="utf-8")
    assert "merge_session_toolsets(_profile_toolsets, _override)" in src
    # The old permissive assignment must be gone from the override branch.
    assert not re.search(r"^\s*_toolsets = _override\s*$", src, re.M)


def test_ui_mirror_of_core_list_matches_server():
    js = (REPO / "static" / "ui.js").read_text(encoding="utf-8")
    m = re.search(r"const CORE_SESSION_TOOLSETS = \[([^\]]*)\]", js)
    assert m, "ui.js must declare CORE_SESSION_TOOLSETS"
    ui_list = [s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()]
    assert ui_list == list(CORE_SESSION_TOOLSETS)
