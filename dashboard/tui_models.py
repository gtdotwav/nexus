"""
NEXUS — TUI Data Models

Bridge between NexusAgent data and Textual widgets.
Provides a simplified, flat snapshot for UI consumption.
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

    # Meta
    uptime_seconds: int = 0

    @classmethod
    def from_agent(cls, agent: "NexusAgent") -> "TUIState":
        """Build TUIState from a live NexusAgent instance."""
        snap = agent.state.get_snapshot()
        char = snap.get("character", {})
        combat = snap.get("combat", {})
        session = snap.get("session", {})

        # ── Consciousness data (all defensive) ──
        emotion_label = ""
        goals: list[dict] = []
        memories: list[dict] = []

        consciousness = getattr(agent, "consciousness", None)
        if consciousness:
            # emotion is a dict[str, float] — pick the dominant one
            raw_emotion = getattr(consciousness, "emotion", {})
            if isinstance(raw_emotion, dict) and raw_emotion:
                top_key = max(raw_emotion, key=raw_emotion.get)
                top_val = raw_emotion[top_key]
                emotion_label = f"{top_key.capitalize()} ({top_val:.0%})" if top_val > 0.1 else ""

            # goals have: description, category, priority, progress
            raw_goals = getattr(consciousness, "active_goals", [])
            for g in raw_goals[:5]:
                goals.append({
                    "text": getattr(g, "description", "?")[:60],
                    "type": getattr(g, "category", "?"),
                    "priority": getattr(g, "priority", 0),
                })

            # memories have: category, content, importance
            raw_memory = getattr(consciousness, "working_memory", None)
            if raw_memory:
                for m in list(raw_memory)[-5:]:
                    memories.append({
                        "type": getattr(m, "category", "?"),
                        "text": getattr(m, "content", "?")[:80],
                        "importance": getattr(m, "importance", 0),
                    })

        pos = char.get("position", {})

        # ── Strategic brain metrics (all defensive) ──
        brain = getattr(agent, "strategic_brain", None)
        b_calls = brain.calls if brain else 0
        b_latency = round(brain.avg_latency_ms) if brain else 0
        b_error = round(brain.error_rate, 3) if brain else 0.0
        b_skipped = brain.skipped_calls if brain else 0
        b_cb = brain.circuit_breaker_state if brain else "CLOSED"

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
            brain_calls=b_calls,
            brain_latency_ms=b_latency,
            brain_error_rate=b_error,
            brain_skipped=b_skipped,
            circuit_breaker=b_cb,
            emotion=emotion_label,
            goals=goals,
            memories=memories,
        )


class DemoSimulator:
    """
    Generates stable, incrementally-evolving demo data.

    Instead of fully random data every 250ms (which causes wild flickering),
    this maintains a persistent state that evolves slowly — kills go up,
    HP fluctuates, new events appear every few seconds.
    """

    CREATURES = ["Rat", "Cyclops", "Dragon Lord", "Demon", "Hydra", "Orc Berserker", "Giant Spider"]
    MODES = ["HUNTING", "LOOTING", "NAVIGATING", "EXPLORING"]
    EMOTIONS = ["Focused", "Confident", "Cautious", "Excited", "Alert"]

    def __init__(self):
        self._state = self._initial_state()
        self._tick: int = 0
        self._last_event_tick: int = 0
        self._last_mode_tick: int = 0

    def _initial_state(self) -> TUIState:
        return TUIState(
            hp=78.5,
            mana=62.3,
            position=(132, 187, 7),
            mode="HUNTING",
            threat="NONE",
            active_skill="rotworm_hunt_v3",
            target="Cyclops",
            battle_list=[
                {"name": "Cyclops", "hp": 65, "dist": 3, "attacking": True},
                {"name": "Rat", "hp": 100, "dist": 6, "attacking": False},
            ],
            xp_hr=145000,
            gold_hr=22000,
            kills=47,
            deaths=0,
            duration_min=35.2,
            close_calls=2,
            brain_calls=142,
            brain_latency_ms=280,
            brain_error_rate=0.012,
            brain_skipped=3,
            circuit_breaker="CLOSED",
            emotion="Focused (85%)",
            goals=[
                {"text": "Hunt efficiently in Cyclopolis", "type": "primary", "priority": 1},
                {"text": "Avoid PK zones near cave exit", "type": "safety", "priority": 2},
            ],
            memories=[
                {"type": "discovery", "text": "Good spawn density at NE corner", "importance": 0.8},
                {"type": "combat", "text": "Close call with 3 cyclops at once", "importance": 0.9},
            ],
            events=[
                "kill: Cyclops",
                "loot: 230 gold",
                "heal: exura (145 hp)",
                "spot: Rat x2",
            ],
            uptime_seconds=2112,
        )

    def tick(self) -> TUIState:
        """Advance simulation by one step (~250ms). Returns stable, evolving state."""
        s = self._state
        self._tick += 1

        # ── Every tick: subtle vital fluctuations ──
        s.hp = max(15, min(100, s.hp + random.uniform(-2, 3)))
        s.mana = max(10, min(100, s.mana + random.uniform(-1.5, 2)))
        s.duration_min += 0.004  # ~1s per 4 ticks
        s.uptime_seconds = int(s.duration_min * 60)

        # ── Every ~3s (12 ticks): add an event, increment stats ──
        if self._tick - self._last_event_tick >= 12:
            self._last_event_tick = self._tick
            creature = random.choice(self.CREATURES)

            event_type = random.choices(
                ["kill", "loot", "heal", "spot", "move"],
                weights=[3, 3, 2, 1, 1],
                k=1,
            )[0]

            if event_type == "kill":
                s.kills += 1
                s.xp_hr = min(350000, s.xp_hr + random.randint(500, 2000))
                evt = f"kill: {creature}"
            elif event_type == "loot":
                gold = random.randint(20, 400)
                s.gold_hr = min(80000, s.gold_hr + random.randint(100, 500))
                evt = f"loot: {gold} gold"
            elif event_type == "heal":
                hp_healed = random.randint(50, 200)
                s.hp = min(100, s.hp + hp_healed * 0.1)
                evt = f"heal: exura ({hp_healed} hp)"
            elif event_type == "spot":
                evt = f"spot: {creature} x{random.randint(1, 3)}"
            else:
                x, y = s.position[0] + random.randint(-3, 3), s.position[1] + random.randint(-3, 3)
                s.position = (x, y, 7)
                evt = f"move: ({x}, {y}, 7)"

            s.events.insert(0, evt)
            if len(s.events) > 30:
                s.events = s.events[:30]

            # Battle list: occasionally add/remove creatures
            if random.random() > 0.7:
                if len(s.battle_list) < 6:
                    s.battle_list.append({
                        "name": random.choice(self.CREATURES),
                        "hp": random.uniform(30, 100),
                        "dist": random.randint(1, 8),
                        "attacking": random.random() > 0.5,
                    })
                elif s.battle_list:
                    s.battle_list.pop(random.randint(0, len(s.battle_list) - 1))

            s.target = s.battle_list[0]["name"] if s.battle_list else None

            # Mutate existing creature HP
            for c in s.battle_list:
                c["hp"] = max(0, min(100, c["hp"] + random.uniform(-15, 5)))

            s.brain_calls += 1

        # ── Every ~20s (80 ticks): mode change ──
        if self._tick - self._last_mode_tick >= 80:
            self._last_mode_tick = self._tick
            s.mode = random.choice(self.MODES)
            s.emotion = f"{random.choice(self.EMOTIONS)} ({random.randint(60, 95)}%)"
            s.events.insert(0, f"mode: {s.mode}")

        # ── Close call: rare event ──
        if s.hp < 25 and random.random() > 0.9:
            s.close_calls += 1
            s.events.insert(0, f"CLOSE CALL: HP {s.hp:.0f}%")

        return s
