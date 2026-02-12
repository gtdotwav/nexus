"""
NEXUS — GameState and state models tests.

Validates: state initialization, enums, models, and state package exports.
"""

from __future__ import annotations

import pytest

from core.state import GameState, AgentMode, ThreatLevel, Position, CreatureState, SupplyCount
from core.state.enums import AgentMode as EnumAgentMode
from core.state.models import Position as ModelPosition


def test_game_state_defaults():
    """GameState should initialize with safe defaults."""
    state = GameState()
    assert state.mode == AgentMode.IDLE
    assert state.threat_level == ThreatLevel.NONE


def test_agent_modes():
    """All expected agent modes should exist."""
    expected = {"IDLE", "HUNTING", "FLEEING", "DEPOSITING", "TRADING", "NAVIGATING", "EXPLORING"}
    actual = {m.name for m in AgentMode}
    assert expected.issubset(actual)


def test_threat_levels():
    """All expected threat levels should exist."""
    expected = {"NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
    actual = {t.name for t in ThreatLevel}
    assert expected.issubset(actual)


def test_position_creation():
    """Position should store x, y, z coordinates."""
    pos = Position(x=100, y=200, z=7)
    assert pos.x == 100
    assert pos.y == 200
    assert pos.z == 7


def test_state_package_re_exports():
    """core.state should re-export all key symbols from submodules."""
    # These imports must work (backward compatibility)
    from core.state import GameState
    from core.state import AgentMode, ThreatLevel
    from core.state import Position

    # Verify they're the same classes
    assert EnumAgentMode is AgentMode
    assert ModelPosition is Position


def test_creature_state():
    """CreatureState should hold creature battle info."""
    creature = CreatureState(
        name="Dragon Lord",
        hp_percent=85,
        distance=3,
        is_player=False,
    )
    assert creature.name == "Dragon Lord"
    assert creature.hp_percent == 85
    assert creature.is_player is False
