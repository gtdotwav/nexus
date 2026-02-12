"""
NEXUS Agent — Real-Time Reasoning Engine

The core intelligence that handles UNKNOWN situations.
This is NOT the strategic brain (Claude API). This is the LOCAL reasoning
system that runs at high frequency with zero API latency.

What it does:
- Pattern inference from spatial memory (creature distributions → danger prediction)
- Dungeon topology reasoning (dead-end detection, corridor vs room, floor layout)
- Threat escalation detection (increasingly dangerous creatures = go deeper carefully)
- Resource efficiency analysis (is this area worth hunting? when to leave?)
- Anomaly detection (new creature never seen before, unusual tile patterns)
- Dynamic risk assessment (combine all signals into a risk score)
- Strategy recommendation (explore? hunt? retreat? skip?)

This gives NEXUS "intuition" — fast, local reasoning that doesn't
wait for the Claude API's 3-second cycle. It's the difference between
a bot that walks into fire and one that anticipates danger.
"""

from __future__ import annotations

import math
import time
import structlog
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState
    from perception.spatial_memory_v2 import SpatialMemoryV2 as SpatialMemory

log = structlog.get_logger()


@dataclass
class Inference:
    """A reasoning inference — a conclusion drawn from data."""
    category: str           # "threat", "opportunity", "topology", "anomaly"
    confidence: float       # 0-1
    description: str
    action_hint: str        # "retreat", "push", "explore", "avoid", "investigate"
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class AreaProfile:
    """Real-time profile of the current area."""
    danger_trend: str = "stable"          # "increasing", "decreasing", "stable"
    creature_difficulty: str = "unknown"  # "easy", "medium", "hard", "lethal"
    topology: str = "unknown"             # "open", "corridor", "room", "maze", "dead_end"
    resource_efficiency: float = 0.0       # XP/risk ratio (higher = better)
    recommended_action: str = "continue"   # "continue", "explore", "retreat", "push_deeper"
    warnings: list = field(default_factory=list)
    opportunities: list = field(default_factory=list)


class ReasoningEngine:
    """
    Local inference engine for real-time decision support.

    Runs every 2-5 seconds (no API calls, pure computation).
    Analyzes spatial memory + game state → produces inferences
    that the reactive brain and strategic brain can use.
    """

    def __init__(self, state: "GameState", spatial_memory: "SpatialMemory"):
        self.state = state
        self.memory = spatial_memory

        # Recent inferences
        self.inferences: deque[Inference] = deque(maxlen=50)
        self.current_profile: AreaProfile = AreaProfile()

        # Tracking for trend detection
        self._danger_history: deque[float] = deque(maxlen=30)
        self._creature_history: deque[dict] = deque(maxlen=20)
        self._hp_history: deque[float] = deque(maxlen=60)
        self._position_history: deque[tuple] = deque(maxlen=100)

        # Known creature danger tiers (learned + hardcoded seed)
        self.creature_tiers: dict[str, int] = {
            # Tier 0: harmless
            "Rat": 0, "Bug": 0, "Snake": 0,
            # Tier 1: easy
            "Rotworm": 1, "Cyclops": 1, "Amazon": 1,
            # Tier 2: medium
            "Dragon": 2, "Giant Spider": 2, "Hydra": 2,
            # Tier 3: hard
            "Dragon Lord": 3, "Demon": 3, "Warlock": 3,
            # Tier 4: lethal
            "Ferumbras": 4, "Orshabaal": 4,
        }

        self._last_analysis: float = 0
        self._analysis_interval: float = 2.0

    async def analyze(self) -> AreaProfile:
        """
        Run full area analysis. Returns an AreaProfile with
        recommendations for the current location.

        Called every 2-5 seconds from the action loop.
        """
        now = time.time()
        if now - self._last_analysis < self._analysis_interval:
            return self.current_profile
        self._last_analysis = now

        pos = self.state.position
        if pos is None:
            return self.current_profile

        # Record position for movement analysis
        self._position_history.append((pos.x, pos.y, pos.z, now))
        self._hp_history.append(self.state.hp_percent)

        # Run all reasoning modules
        profile = AreaProfile()

        self._analyze_danger_trend(pos, profile)
        self._analyze_creature_difficulty(pos, profile)
        self._analyze_topology(pos, profile)
        self._analyze_resource_efficiency(pos, profile)
        self._detect_anomalies(pos, profile)
        self._compute_recommendation(profile)

        self.current_profile = profile
        return profile

    def _analyze_danger_trend(self, pos, profile: AreaProfile):
        """
        Is this area getting more or less dangerous over time?
        Uses rolling window of danger scores.
        """
        current_danger = self.memory.get_area_danger(pos.x, pos.y, pos.z, radius=5)
        self._danger_history.append(current_danger)

        if len(self._danger_history) < 5:
            profile.danger_trend = "unknown"
            return

        # Compare recent vs older danger
        recent = list(self._danger_history)[-5:]
        older = list(self._danger_history)[:-5] if len(self._danger_history) > 5 else recent

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)

        if avg_recent > avg_older + 0.1:
            profile.danger_trend = "increasing"
            if avg_recent > 0.6:
                profile.warnings.append("Danger escalating rapidly")
                self._add_inference("threat", 0.7,
                    f"Area danger increasing: {avg_older:.2f} → {avg_recent:.2f}",
                    "retreat")
        elif avg_recent < avg_older - 0.1:
            profile.danger_trend = "decreasing"
        else:
            profile.danger_trend = "stable"

    def _analyze_creature_difficulty(self, pos, profile: AreaProfile):
        """
        Assess creature difficulty in current area.
        Uses known tiers + inference from death data.
        """
        creatures = self.memory.get_creatures_in_area(pos.x, pos.y, pos.z, radius=8)
        self._creature_history.append(creatures)

        if not creatures:
            profile.creature_difficulty = "empty"
            return

        # Calculate average tier
        total_weight = 0
        total_tier = 0

        for creature, count in creatures.items():
            tier = self.creature_tiers.get(creature, -1)

            if tier == -1:
                # UNKNOWN creature — this is where inference happens
                tier = self._infer_creature_tier(creature, pos)
                self.creature_tiers[creature] = tier
                self._add_inference("anomaly", 0.8,
                    f"New creature discovered: {creature} (inferred tier {tier})",
                    "investigate")

            total_tier += tier * count
            total_weight += count

        if total_weight > 0:
            avg_tier = total_tier / total_weight
            if avg_tier <= 0.5:
                profile.creature_difficulty = "easy"
            elif avg_tier <= 1.5:
                profile.creature_difficulty = "medium"
            elif avg_tier <= 2.5:
                profile.creature_difficulty = "hard"
            else:
                profile.creature_difficulty = "lethal"
                profile.warnings.append(f"Lethal creatures detected (avg tier {avg_tier:.1f})")

        # Detect difficulty escalation (going deeper into dungeon)
        if len(self._creature_history) >= 3:
            recent_creatures = self._creature_history[-1]
            older_creatures = self._creature_history[-3]

            recent_tiers = [self.creature_tiers.get(c, 1) for c in recent_creatures]
            older_tiers = [self.creature_tiers.get(c, 1) for c in older_creatures]

            if recent_tiers and older_tiers:
                recent_avg = sum(recent_tiers) / len(recent_tiers)
                older_avg = sum(older_tiers) / len(older_tiers)

                if recent_avg > older_avg + 0.5:
                    self._add_inference("threat", 0.6,
                        f"Creature difficulty escalating: tier {older_avg:.1f} → {recent_avg:.1f}. "
                        "Likely going deeper into dungeon.",
                        "caution")

    def _infer_creature_tier(self, creature_name: str, pos) -> int:
        """
        Infer the danger tier of a never-before-seen creature.
        Uses context clues:
        - Floor depth (deeper = harder)
        - Surrounding creature tiers (similar area = similar difficulty)
        - Name patterns ("Lord", "King", "Ancient" = harder)
        - Death data at this location
        """
        # Signal 1: Floor depth (z=7 is surface, z=8 is -1, etc.)
        depth_tier = max(0, pos.z - 7)

        # Signal 2: Area creature tiers
        area_creatures = self.memory.get_creatures_in_area(pos.x, pos.y, pos.z, radius=10)
        known_tiers = [self.creature_tiers[c] for c in area_creatures
                        if c in self.creature_tiers and c != creature_name]
        area_avg_tier = sum(known_tiers) / max(1, len(known_tiers)) if known_tiers else 1

        # Signal 3: Name-based heuristics
        name_upper = creature_name.lower()
        name_bonus = 0
        danger_words = ["lord", "king", "ancient", "dire", "elder", "war", "demon",
                        "dark", "shadow", "death", "hell", "undead", "dragon"]
        for word in danger_words:
            if word in name_upper:
                name_bonus += 1

        # Signal 4: Death data
        area_deaths = 0
        if pos.z in self.memory.floors:
            floor_data = self.memory.floors[pos.z]
            for dx in range(-5, 6):
                for dy in range(-5, 6):
                    cell = floor_data.get((pos.x + dx, pos.y + dy))
                    if cell and hasattr(cell, "death_count"):
                        area_deaths += cell.death_count
        death_bonus = min(2, area_deaths * 0.3)

        # Combine signals
        inferred = round(
            depth_tier * 0.3 + area_avg_tier * 0.3 +
            name_bonus * 0.2 + death_bonus * 0.2
        )
        inferred = max(0, min(4, inferred))

        log.info("reasoning.inferred_creature_tier",
                 creature=creature_name, tier=inferred,
                 signals={"depth": depth_tier, "area": round(area_avg_tier, 1),
                          "name": name_bonus, "deaths": round(death_bonus, 1)})

        return inferred

    def _analyze_topology(self, pos, profile: AreaProfile):
        """
        Determine the topology of the current area.
        Corridor? Open room? Dead end? Maze?
        """
        if pos.z not in self.memory.floors:
            profile.topology = "unknown"
            return

        floor = self.memory.floors[pos.z]

        # Count walkable neighbors in expanding rings
        walkable_ring1 = 0  # Adjacent (8 cells)
        walkable_ring2 = 0  # 2-tile radius (24 cells)
        total_ring1 = 0
        total_ring2 = 0

        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx == 0 and dy == 0:
                    continue
                key = (pos.x + dx, pos.y + dy)
                cell = floor.cells.get(key)
                if cell is None:
                    continue  # Unexplored — don't count
                ring = 1 if abs(dx) <= 1 and abs(dy) <= 1 else 2

                if ring == 1:
                    total_ring1 += 1
                    if cell.walkable:
                        walkable_ring1 += 1
                else:
                    total_ring2 += 1
                    if cell.walkable:
                        walkable_ring2 += 1

        ratio1 = walkable_ring1 / max(1, total_ring1)
        ratio2 = walkable_ring2 / max(1, total_ring2)

        if ratio1 < 0.3:
            profile.topology = "dead_end"
            profile.warnings.append("Dead end detected — limited escape routes")
        elif ratio1 < 0.5 and ratio2 < 0.5:
            profile.topology = "corridor"
        elif ratio1 > 0.7 and ratio2 > 0.6:
            profile.topology = "open"
        elif ratio1 > 0.5:
            profile.topology = "room"
        else:
            profile.topology = "maze"

        # Dead end + high danger = trap
        if profile.topology == "dead_end" and self.memory.get_area_danger(pos.x, pos.y, pos.z) > 0.4:
            self._add_inference("threat", 0.8,
                "Dead end in dangerous area — potential trap. Retreat recommended.",
                "retreat")

    def _analyze_resource_efficiency(self, pos, profile: AreaProfile):
        """
        Is this area worth the risk?
        Calculate XP-to-danger ratio based on observed data.
        """
        area_value = self.memory.get_area_value(pos.x, pos.y, pos.z, radius=8)
        area_danger = self.memory.get_area_danger(pos.x, pos.y, pos.z, radius=8)

        # Efficiency = value / (1 + danger)
        efficiency = area_value / (1 + area_danger * 3)
        profile.resource_efficiency = round(efficiency, 3)

        if efficiency > 0.5:
            profile.opportunities.append(f"High-efficiency area (ratio={efficiency:.2f})")
        elif efficiency < 0.1 and area_danger > 0.3:
            profile.warnings.append(f"Low efficiency for danger level (ratio={efficiency:.2f})")

    def _detect_anomalies(self, pos, profile: AreaProfile):
        """Detect unusual patterns that deserve attention."""

        # Anomaly 1: Sudden HP drops (damage spike)
        if len(self._hp_history) >= 5:
            recent_hp = list(self._hp_history)[-5:]
            hp_drop = max(recent_hp) - min(recent_hp)
            if hp_drop > 40:
                self._add_inference("threat", 0.9,
                    f"Sudden HP drop of {hp_drop:.0f}% detected — "
                    "possible strong attack or multiple creature pull",
                    "retreat")
                profile.warnings.append(f"HP spike: {hp_drop:.0f}% damage burst")

        # Anomaly 2: Movement stall (stuck or cornered)
        if len(self._position_history) >= 10:
            recent_pos = list(self._position_history)[-10:]
            unique_positions = len(set((p[0], p[1]) for p in recent_pos))
            if unique_positions <= 2:
                self._add_inference("topology", 0.6,
                    "Movement stalled — possibly stuck, cornered, or surrounded",
                    "investigate")

        # Anomaly 3: Never-seen-before floor
        known_floors = set(self.memory.floors.keys())
        if pos.z not in known_floors:
            self._add_inference("anomaly", 0.9,
                f"Entered completely unknown floor z={pos.z}. "
                "No spatial data available. Maximum caution.",
                "caution")
            profile.warnings.append(f"Unknown floor z={pos.z}")

    def _compute_recommendation(self, profile: AreaProfile):
        """
        Synthesize all signals into a final recommendation.
        """
        score = 0

        # Positive signals → push/explore
        if profile.resource_efficiency > 0.3:
            score += 2
        if profile.creature_difficulty in ("easy", "medium"):
            score += 1
        if profile.danger_trend == "decreasing":
            score += 1
        if profile.topology in ("open", "room"):
            score += 1

        # Negative signals → retreat
        if profile.creature_difficulty == "lethal":
            score -= 3
        if profile.danger_trend == "increasing":
            score -= 2
        if profile.topology == "dead_end":
            score -= 2
        if len(profile.warnings) >= 2:
            score -= 1

        # Decide
        if score >= 3:
            profile.recommended_action = "push_deeper"
        elif score >= 1:
            profile.recommended_action = "continue"
        elif score >= -1:
            profile.recommended_action = "explore"
        else:
            profile.recommended_action = "retreat"

    def _add_inference(self, category: str, confidence: float,
                       description: str, action_hint: str):
        """Record an inference for the strategic brain to consume."""
        inference = Inference(
            category=category,
            confidence=confidence,
            description=description,
            action_hint=action_hint,
        )
        self.inferences.append(inference)

        if confidence >= 0.7:
            log.info("reasoning.inference",
                     category=category,
                     confidence=confidence,
                     description=description[:80],
                     hint=action_hint)

    def get_recent_inferences(self, max_age_s: float = 60,
                                category: str = "") -> list[Inference]:
        """Get recent inferences, optionally filtered by category."""
        cutoff = time.time() - max_age_s
        result = [i for i in self.inferences if i.timestamp >= cutoff]
        if category:
            result = [i for i in result if i.category == category]
        return result

    def get_reasoning_context(self) -> str:
        """
        Build compact context string for the strategic brain.
        Feeds local reasoning results into Claude's thinking.
        """
        if self.current_profile is None:
            return "[LOCAL REASONING]\nNo analysis yet"

        p = self.current_profile
        lines = [
            f"[LOCAL REASONING]",
            f"Danger:{p.danger_trend} Difficulty:{p.creature_difficulty} "
            f"Topology:{p.topology} Efficiency:{p.resource_efficiency}",
            f"Action:{p.recommended_action}",
        ]

        if p.warnings:
            lines.append(f"WARNINGS: {'; '.join(p.warnings[:3])}")
        if p.opportunities:
            lines.append(f"OPPORTUNITIES: {'; '.join(p.opportunities[:2])}")

        # Recent high-confidence inferences
        recent = self.get_recent_inferences(max_age_s=30)
        high_conf = [i for i in recent if i.confidence >= 0.6]
        if high_conf:
            inf_str = " | ".join(f"{i.category}:{i.description[:50]}" for i in high_conf[-3:])
            lines.append(f"Inferences: {inf_str}")

        return "\n".join(lines)

    @property
    def stats(self) -> dict:
        return {
            "total_inferences": len(self.inferences),
            "known_creatures": len(self.creature_tiers),
            "current_action": self.current_profile.recommended_action,
            "danger_trend": self.current_profile.danger_trend,
            "topology": self.current_profile.topology,
        }
