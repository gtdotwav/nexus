"""
NEXUS — TUI Data Models

Bridge between NexusAgent data and Textual widgets.
Provides a simplified, immutable snapshot for UI consumption.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent


@dataclass
class TUIState:
    """Flat snapshot of all agent data for widget consumption."""

    # Character vitals
    hp: float = 100.0
    mana: float = 100.0
    position: tuple[int, int, int] = (0, 0, 0)
    is_alive: bool = True

    # Agent
    mode: str = "IDLE"
    threat: str = "NONE"
    active_skill: str = "None"
    game: str = "tibia"
    version: str = "0.4.2"

    # Combat
    target: Optional[str] = None
    battle_list: list[dict] = field(default_factory=list)
    nearby_players: list[dict] = field(default_factory=list)

    # Session
    xp_hr: int = 0
    gold_hr: int = 0
    kills: int = 0
    deaths: int = 0
    duration_min: float = 0.0
    close_calls: int = 0

    # Strategic brain
    brain_calls: int = 0
    brain_latency_ms: int = 0
    brain_error_rate: float = 0.0
    brain_skipped: int = 0
    circuit_breaker: str = "CLOSED"

    # Consciousness
    emotion: str = ""
    goals: list[dict] = field(default_factory=list)
    memories: list[dict] = field(default_factory=list)

    # Events (most recent first)
    events: list[str] = field(default_factory=list)

    # Dashboard connections
    ws_clients: int = 0
    uptime_seconds: int = 0

    @classmethod
    def from_agent(cls, agent: "NexusAgent") -> "TUIState":
        """Build TUIState from a live NexusAgent instance."""
        snap = agent.state.get_snapshot()
        char = snap.get("character", {})
        combat = snap.get("combat", {})
        session = snap.get("session", {})

        # Consciousness data
        emotion = ""
        goals: list[dict] = []
        memories: list[dict] = []
        if agent.consciousness:
            emotion = getattr(agent.consciousness, "emotional_state", "")
            if hasattr(agent.consciousness, "active_goals"):
                goals = [
                    {"text": g.text, "type": g.type, "priority": g.priority}
                    for g in agent.consciousness.active_goals[:5]
                ]
            if hasattr(agent.consciousness, "working_memory"):
                memories = [
                    {"type": m.category, "text": m.content[:80], "importance": m.importance}
                    for m in list(agent.consciousness.working_memory)[-5:]
                ]

        pos = char.get("position", {})

        return cls(
            hp=char.get("hp_percent", 100),
            mana=char.get("mana_percent", 100),
            position=(pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)),
            is_alive=char.get("is_alive", True),
            mode=combat.get("mode", "IDLE"),
            threat=combat.get("threat_level", "NONE"),
            active_skill=snap.get("active_skill") or "None",
            game=getattr(agent, "_game_id", "tibia"),
            target=combat.get("current_target"),
            battle_list=combat.get("battle_list", [])[:8],
            nearby_players=combat.get("nearby_players", []),
            xp_hr=round(session.get("xp_per_hour", 0)),
            gold_hr=round(session.get("profit_per_hour", 0)),
            kills=session.get("kills", 0),
            deaths=session.get("deaths", 0),
            duration_min=round(session.get("duration_minutes", 0), 1),
            close_calls=session.get("close_calls", 0),
            brain_calls=agent.strategic_brain.calls if hasattr(agent, "strategic_brain") else 0,
            brain_latency_ms=round(agent.strategic_brain.avg_latency_ms) if hasattr(agent, "strategic_brain") else 0,
            brain_error_rate=round(agent.strategic_brain.error_rate, 3) if hasattr(agent, "strategic_brain") else 0,
            brain_skipped=agent.strategic_brain.skipped_calls if hasattr(agent, "strategic_brain") else 0,
            circuit_breaker=agent.strategic_brain.circuit_breaker_state if hasattr(agent, "strategic_brain") else "CLOSED",
            emotion=emotion,
            goals=goals,
            memories=memories,
            ws_clients=0,
        )

    @classmethod
    def demo(cls) -> "TUIState":
        """Generate simulated data for demo/preview mode."""
        modes = ["HUNTING", "LOOTING", "NAVIGATING", "HEALING_CRITICAL", "EXPLORING"]
        threats = ["NONE", "LOW", "MEDIUM"]
        emotions = ["Focused", "Confident", "Cautious", "Excited", "Alert"]
        creatures = ["Rat", "Cyclops", "Dragon Lord", "Demon", "Hydra", "Orc Berserker", "Giant Spider"]

        hp = random.uniform(25, 100)
        battle = [
            {"name": random.choice(creatures), "hp": random.uniform(10, 100), "dist": random.randint(1, 8), "attacking": random.random() > 0.6}
            for _ in range(random.randint(0, 5))
        ]

        events = [
            f"kill: {random.choice(creatures)}",
            f"loot: {random.randint(10, 500)} gold",
            f"heal: exura ({random.randint(50, 200)} hp)",
            f"move: ({random.randint(100, 200)}, {random.randint(100, 200)}, 7)",
            f"mode: {random.choice(modes)}",
            f"spot: {random.choice(creatures)} x{random.randint(1, 4)}",
        ]

        return cls(
            hp=round(hp, 1),
            mana=round(random.uniform(30, 100), 1),
            position=(random.randint(100, 250), random.randint(100, 250), 7),
            mode=random.choice(modes),
            threat=random.choice(threats),
            active_skill="rotworm_hunt_v3",
            target=battle[0]["name"] if battle else None,
            battle_list=battle,
            xp_hr=random.randint(80000, 250000),
            gold_hr=random.randint(5000, 50000),
            kills=random.randint(50, 500),
            deaths=random.randint(0, 2),
            duration_min=round(random.uniform(10, 180), 1),
            close_calls=random.randint(0, 8),
            brain_calls=random.randint(100, 2000),
            brain_latency_ms=random.randint(150, 600),
            brain_error_rate=round(random.uniform(0, 0.05), 3),
            brain_skipped=random.randint(0, 50),
            circuit_breaker="CLOSED",
            emotion=random.choice(emotions),
            goals=[
                {"text": "Hunt efficiently in Cyclopolis", "type": "primary", "priority": 1},
                {"text": "Avoid PK zones", "type": "safety", "priority": 2},
            ],
            memories=[
                {"type": "discovery", "text": "Found good spawn at NE corner", "importance": 0.8},
                {"type": "combat", "text": "Close call with 3 cyclops", "importance": 0.9},
            ],
            events=random.sample(events, k=min(4, len(events))),
            uptime_seconds=random.randint(600, 10800),
        )
