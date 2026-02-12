"""NEXUS — Game state data models.

Add new dataclasses here. This file is safe to edit without
affecting GameState or other modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    x: int = 0
    y: int = 0
    z: int = 7  # Default floor level in Tibia


@dataclass
class CreatureState:
    name: str
    hp_percent: float
    distance: int
    is_attacking: bool = False
    is_player: bool = False
    skull: Optional[str] = None  # white, red, black, etc.
    last_seen: float = 0.0


@dataclass
class SupplyCount:
    great_health_potions: int = 0
    great_mana_potions: int = 0
    great_spirit_potions: int = 0
    ultimate_health_potions: int = 0
    ammunition: int = 0
    runes: int = 0


@dataclass
class SessionMetrics:
    start_time: float = 0.0
    xp_gained: int = 0
    xp_per_hour: float = 0.0
    loot_value: int = 0
    profit_per_hour: float = 0.0
    deaths: int = 0
    kills: int = 0
    supplies_used: int = 0
    close_calls: int = 0  # Times HP dropped below critical


@dataclass
class CombatLogEntry:
    timestamp: float
    event_type: str  # "damage_taken", "damage_dealt", "heal", "death", "kill"
    source: str
    target: str
    value: int
    details: str = ""
