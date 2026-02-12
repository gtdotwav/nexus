"""
NEXUS — Game State Package

Backward-compatible re-exports. ALL existing imports like
    from core.state import GameState, AgentMode
continue to work exactly as before.

Internal structure:
    core/state/enums.py      → AgentMode, ThreatLevel
    core/state/models.py     → Position, CreatureState, SupplyCount, SessionMetrics, CombatLogEntry
    core/state/game_state.py → GameState
"""

from core.state.enums import AgentMode, ThreatLevel
from core.state.models import (
    Position,
    CreatureState,
    SupplyCount,
    SessionMetrics,
    CombatLogEntry,
)
from core.state.game_state import GameState

__all__ = [
    "AgentMode",
    "ThreatLevel",
    "Position",
    "CreatureState",
    "SupplyCount",
    "SessionMetrics",
    "CombatLogEntry",
    "GameState",
]
