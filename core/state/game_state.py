"""
NEXUS Agent - Game State Manager

Central state store that all components read from and write to.
Thread-safe, fast access, with change notification system.

WARNING: 13 files import from this module. Any change here
must be verified against all dependents:
    grep -r "from core.state" --include="*.py" .
"""

from __future__ import annotations

import time
import threading
import structlog
from typing import Optional, Callable
from collections import deque

from core.state.enums import AgentMode, ThreatLevel
from core.state.models import (
    Position, CreatureState, SupplyCount,
    SessionMetrics, CombatLogEntry,
)

log = structlog.get_logger()


class GameState:
    """
    Thread-safe central game state.
    All perception modules write here.
    All brain modules read from here.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._listeners: dict[str, list[Callable]] = {}

        # Character stats
        self.hp: float = 100.0
        self.hp_max: float = 100.0
        self.mana: float = 100.0
        self.mana_max: float = 100.0
        self.soul: int = 100

        # Position
        self.position: Position = Position()
        self.floor_level: int = 7

        # Agent state
        self.mode: AgentMode = AgentMode.IDLE
        self.threat_level: ThreatLevel = ThreatLevel.NONE
        self.is_alive: bool = True

        # Creatures & players on screen
        self.battle_list: list[CreatureState] = []
        self.current_target: Optional[CreatureState] = None
        self.nearby_players: list[CreatureState] = []

        # Supplies
        self.supplies: SupplyCount = SupplyCount()

        # Combat log (last 100 entries)
        self.combat_log: deque[CombatLogEntry] = deque(maxlen=100)

        # Session tracking
        self.session: SessionMetrics = SessionMetrics(start_time=time.time())

        # Active skill info
        self.active_skill: Optional[str] = None
        self.current_waypoint_index: int = 0

        # Cooldowns (spell_name -> timestamp when available)
        self.cooldowns: dict[str, float] = {}

        # Timestamps
        self.last_perception_update: float = 0.0
        self.last_strategic_update: float = 0.0
        self.last_action: float = 0.0

    @property
    def hp_percent(self) -> float:
        if self.hp_max == 0:
            return 0
        return (self.hp / self.hp_max) * 100

    @property
    def mana_percent(self) -> float:
        if self.mana_max == 0:
            return 0
        return (self.mana / self.mana_max) * 100

    @property
    def session_duration_minutes(self) -> float:
        return (time.time() - self.session.start_time) / 60

    def update_hp(self, current: float, maximum: float):
        with self._lock:
            old_percent = self.hp_percent
            self.hp = current
            self.hp_max = maximum
            new_percent = self.hp_percent

            if new_percent < 30 and old_percent >= 30:
                self.session.close_calls += 1

            self._notify("hp_changed", {"old": old_percent, "new": new_percent})

    def update_mana(self, current: float, maximum: float):
        with self._lock:
            self.mana = current
            self.mana_max = maximum
            self._notify("mana_changed")

    def update_position(self, x: int, y: int, z: int):
        with self._lock:
            self.position = Position(x=x, y=y, z=z)
            self.floor_level = z
            self._notify("position_changed")

    def update_battle_list(self, creatures: list[CreatureState]):
        with self._lock:
            self.battle_list = creatures
            self.nearby_players = [c for c in creatures if c.is_player]

            hostile_players = [
                p for p in self.nearby_players
                if p.skull in ("white", "red", "black") or p.is_attacking
            ]
            if len(hostile_players) >= 2:
                self.threat_level = ThreatLevel.CRITICAL
            elif hostile_players:
                self.threat_level = ThreatLevel.HIGH
            elif self.nearby_players:
                self.threat_level = ThreatLevel.LOW
            else:
                self.threat_level = ThreatLevel.NONE

            self._notify("battle_list_changed")

    def update_supplies(self, supplies: SupplyCount):
        with self._lock:
            self.supplies = supplies
            self._notify("supplies_changed")

    def add_combat_event(self, entry: CombatLogEntry):
        with self._lock:
            self.combat_log.append(entry)
            if entry.event_type == "death" and entry.target == "self":
                self.session.deaths += 1
                self.is_alive = False
                self._notify("death", {
                    "cause": entry.source,
                    "details": entry.details,
                    "value": entry.value,
                })
            elif entry.event_type == "kill":
                self.session.kills += 1
                self._notify("kill", {
                    "creature": entry.target,
                    "source": entry.source,
                    "value": entry.value,
                })
            self._notify("combat_event", {
                "type": entry.event_type,
                "source": entry.source,
                "target": entry.target,
                "value": entry.value,
            })

    def is_spell_ready(self, spell_name: str) -> bool:
        with self._lock:
            return self.cooldowns.get(spell_name, 0) <= time.time()

    def set_cooldown(self, spell_name: str, duration_ms: int):
        with self._lock:
            self.cooldowns[spell_name] = time.time() + (duration_ms / 1000)

    def set_mode(self, mode: AgentMode):
        with self._lock:
            old_mode = self.mode
            self.mode = mode
            self._notify("mode_changed", {"old": old_mode, "new": mode})

    def get_snapshot(self) -> dict:
        """Full state snapshot for the strategic brain."""
        with self._lock:
            return {
                "timestamp": time.time(),
                "character": {
                    "hp_percent": round(self.hp_percent, 1),
                    "mana_percent": round(self.mana_percent, 1),
                    "soul": self.soul,
                    "position": {"x": self.position.x, "y": self.position.y, "z": self.position.z},
                    "is_alive": self.is_alive,
                },
                "combat": {
                    "mode": self.mode.name,
                    "threat_level": self.threat_level.name,
                    "battle_list": [
                        {"name": c.name, "hp": c.hp_percent, "dist": c.distance, "attacking": c.is_attacking}
                        for c in self.battle_list[:10]
                    ],
                    "current_target": self.current_target.name if self.current_target else None,
                    "nearby_players": [
                        {"name": p.name, "skull": p.skull, "dist": p.distance}
                        for p in self.nearby_players
                    ],
                },
                "supplies": {
                    "health_potions": self.supplies.great_health_potions,
                    "mana_potions": self.supplies.great_mana_potions,
                },
                "session": {
                    "duration_minutes": round(self.session_duration_minutes, 1),
                    "xp_per_hour": round(self.session.xp_per_hour),
                    "profit_per_hour": round(self.session.profit_per_hour),
                    "deaths": self.session.deaths,
                    "kills": self.session.kills,
                    "close_calls": self.session.close_calls,
                },
                "active_skill": self.active_skill,
                "waypoint_index": self.current_waypoint_index,
                "recent_combat": [
                    {"type": e.event_type, "source": e.source, "value": e.value, "time": e.timestamp}
                    for e in list(self.combat_log)[-10:]
                ],
            }

    # Event system for reactive responses
    def on(self, event: str, callback: Callable):
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def _notify(self, event: str, data: dict = None):
        # Copy to avoid issues if listeners modify the list during iteration
        callbacks = self._listeners.get(event, [])[:]
        for callback in callbacks:
            try:
                callback(data or {})
            except Exception as e:
                log.error("state.listener_error", event=event, error=str(e),
                          handler=getattr(callback, "__name__", str(callback)))
