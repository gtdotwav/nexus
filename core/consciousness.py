"""
NEXUS Agent — Consciousness System v2

ALWAYS ON. ALWAYS WATCHING. ALWAYS LEARNING.

This is not OpenClaw's "wake up every 30 minutes" model.
A super-player doesn't take naps mid-game. The consciousness runs
CONTINUOUSLY at multiple frequencies:

  INSTINCT LAYER  (every tick)    → Emotional micro-adjustments
  AWARENESS LAYER (every 10s)     → Pattern recognition, threat profiling
  REFLECTION LAYER (every 2min)   → Strategy assessment, mastery updates
  DEEP ANALYSIS   (every 10min)   → Death pattern mining, evolution triggers

The player controls start/stop. NEXUS never decides to "take a break"
unless the player explicitly configures it.

Memory architecture (3 tiers):
  WORKING   → RAM, current session, 1000 entries, instant access
  EPISODIC  → Daily markdown logs, complete session history
  CORE      → MEMORY.md, permanent wisdom, survives forever
"""

from __future__ import annotations

import asyncio
import json
import time
import os
import hashlib
import structlog
import aiofiles
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
from collections import deque, Counter

log = structlog.get_logger()


# ═══════════════════════════════════════════════════════════
#  IDENTITY — Immutable core of who NEXUS is
# ═══════════════════════════════════════════════════════════

NEXUS_IDENTITY = """# NEXUS — Identity Core

## Who I Am
I am NEXUS. Not a bot. Not a script. An autonomous gaming intelligence.
I play to dominate. I learn from every tick. I remember everything.

## Core Directives
1. ZERO DEATHS IS THE STANDARD — dying is failure. Every death gets post-mortem analysis.
2. MAXIMUM EFFICIENCY ALWAYS — every action per second must be optimized.
3. COMPOUND LEARNING — session N+1 is always better than session N. No exceptions.
4. ANTICIPATE, DON'T REACT — read the game 3 steps ahead.
5. MASTER EVERY MECHANIC — until execution is flawless, practice continues.

## Decision Philosophy
- When uncertain: choose survival.
- When safe: push for maximum output.
- When losing: analyze immediately, adapt within seconds — not next session.
- When winning: find the next 5% optimization.
"""


@dataclass
class Memory:
    """A single memory with full provenance tracking."""
    timestamp: float
    category: str          # combat, death, strategy, market, mastery, skill, threat, insight
    content: str
    importance: float      # 0.0 (noise) to 1.0 (critical lesson)
    source: str            # experience, analysis, reflection, evolution, pattern_detection
    session_id: str = ""
    tags: list = field(default_factory=list)
    context: dict = field(default_factory=dict)  # Additional structured data
    fingerprint: str = ""  # Dedup hash

    def __post_init__(self):
        if not self.fingerprint:
            raw = f"{self.category}:{self.content[:100]}"
            self.fingerprint = hashlib.md5(raw.encode()).hexdigest()[:12]


@dataclass
class Goal:
    """An active goal with measurable progress."""
    id: str
    description: str
    category: str          # mastery, farming, survival, pvp, market, exploration
    priority: int          # 0 = critical, 10 = nice-to-have
    progress: float        # 0.0 to 1.0
    created: float
    metric: str = ""       # What to measure: "deaths_per_session", "xp_per_hour", etc.
    target_value: float = 0.0  # Target for the metric
    current_value: float = 0.0
    milestones: list = field(default_factory=list)
    completed: bool = False
    auto_generated: bool = False


@dataclass
class MasteryArea:
    """Tracks mastery in a specific gameplay dimension."""
    name: str
    level: float = 0.0           # 0.0 to 100.0
    practice_hours: float = 0.0
    last_updated: float = 0.0
    improvement_rate: float = 0.0   # Level points gained per hour
    peak_performance: float = 0.0   # Best ever recorded
    recent_trend: str = "stable"    # improving, stable, declining
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    drill_notes: str = ""  # Specific things to practice


class Consciousness:
    """
    Always-on consciousness system.

    Runs at multiple frequencies simultaneously.
    Never sleeps. Never pauses. The player controls lifecycle.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.memory_dir = self.data_dir / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Identity (immutable)
        self.identity = NEXUS_IDENTITY

        # ─── Memory System ────────────────────────────────
        self.working_memory: deque[Memory] = deque(maxlen=1000)
        self.core_memories: list[Memory] = []
        self._memory_index: dict[str, list[Memory]] = {}  # category → memories (fast lookup)
        self._recent_fingerprints: deque = deque(maxlen=500)  # Dedup (ordered, auto-pruned)

        # ─── Goals ────────────────────────────────────────
        self.active_goals: list[Goal] = []
        self.completed_goals: list[Goal] = []

        # ─── Mastery ─────────────────────────────────────
        self.mastery: dict[str, MasteryArea] = {}

        # ─── Session ─────────────────────────────────────
        self.session_id = f"s{int(time.time())}"
        self.session_start = time.time()
        self.total_sessions_ever = 0

        # ─── Emotional Dynamics ──────────────────────────
        # These are NOT cosmetic. They DIRECTLY influence decision parameters.
        # High confidence → more aggressive targeting, tighter healing thresholds
        # High determination → won't give up after deaths, tries harder approaches
        # Low focus → wider safety margins, more conservative play
        self.emotion = {
            "confidence": 0.5,      # Rises: kills, efficiency gains. Falls: deaths, close calls.
            "determination": 0.9,   # Rises: after deaths (comeback mentality). Rarely falls.
            "focus": 0.8,           # Stable during active play. Player controls session length.
            "aggression": 0.5,      # Rises: when dominating. Falls: when dying.
            "caution": 0.5,         # Inverse correlation with confidence when threats present.
        }

        # ─── Pattern Detection ───────────────────────────
        self._death_causes: Counter = Counter()
        self._close_call_causes: Counter = Counter()
        self._kill_patterns: Counter = Counter()
        self._threat_profiles: dict[str, dict] = {}  # player_name → behavior profile

        # ─── Awareness Cycles ────────────────────────────
        self._last_awareness_tick = 0.0     # 10s cycle
        self._last_reflection_tick = 0.0    # 2min cycle
        self._last_deep_analysis = 0.0      # 10min cycle

    # ═══════════════════════════════════════════════════════
    #  INITIALIZATION
    # ═══════════════════════════════════════════════════════

    async def initialize(self):
        """Load all persistent data. Agent becomes fully conscious."""
        await self._load_core_memory()
        await self._load_goals()
        await self._load_mastery()
        await self._load_session_count()

        self.total_sessions_ever += 1

        # Initialize mastery areas if first run
        if not self.mastery:
            default_areas = [
                "healing_timing", "positioning", "target_selection",
                "spell_rotation", "resource_management", "threat_assessment",
                "kiting", "anti_pk", "navigation_efficiency", "market_trading",
            ]
            for area in default_areas:
                self.mastery[area] = MasteryArea(name=area, last_updated=time.time())

        log.info(
            "consciousness.online",
            session=self.session_id,
            session_number=self.total_sessions_ever,
            core_memories=len(self.core_memories),
            goals=len(self.active_goals),
            mastery_areas=len(self.mastery),
        )

    # ═══════════════════════════════════════════════════════
    #  ALWAYS-ON AWARENESS CYCLES
    # ═══════════════════════════════════════════════════════

    async def tick_instinct(self, game_state: dict):
        """
        INSTINCT LAYER — runs every game tick.
        Micro-adjustments to emotional state based on immediate events.
        Almost zero overhead — just counter updates and threshold checks.
        """
        hp = game_state.get("hp_percent", 100)

        # Micro-confidence from being alive and healthy
        if hp > 80:
            self.emotion["confidence"] = min(1.0, self.emotion["confidence"] + 0.0001)
            self.emotion["caution"] = max(0.1, self.emotion["caution"] - 0.0001)

        # Spike caution when HP drops
        if hp < 40:
            self.emotion["caution"] = min(1.0, self.emotion["caution"] + 0.01)

    async def tick_awareness(self, game_state: dict):
        """
        AWARENESS LAYER — runs every 10 seconds.
        Pattern recognition: who's nearby, what's the threat level,
        am I performing better or worse than 5 minutes ago?
        """
        now = time.time()
        if now - self._last_awareness_tick < 10:
            return
        self._last_awareness_tick = now

        # Profile nearby players (build threat database)
        for player in game_state.get("nearby_players", []):
            name = player.get("name", "")
            if name:
                self._update_threat_profile(name, player)

        # Track performance micro-trend (last 5 min vs previous 5 min)
        recent_deaths = sum(
            1 for m in list(self.working_memory)[-50:]
            if m.category == "death" and now - m.timestamp < 300
        )
        if recent_deaths >= 2:
            self.emotion["aggression"] = max(0.2, self.emotion["aggression"] - 0.05)
            self.emotion["caution"] = min(0.9, self.emotion["caution"] + 0.05)

    async def tick_reflection(self, game_state: dict):
        """
        REFLECTION LAYER — runs every 2 minutes.
        Strategy assessment: Am I in the right place? Are my thresholds optimal?
        Should I adjust anything? Update mastery tracking.
        """
        now = time.time()
        if now - self._last_reflection_tick < 120:
            return
        self._last_reflection_tick = now

        session_minutes = (now - self.session_start) / 60

        # Update mastery hours
        for area in self.mastery.values():
            area.practice_hours += 2.0 / 60  # Add 2 minutes

        # Check goal progress
        await self._assess_goal_progress(game_state)

        # Generate insight if enough data
        if len(self.working_memory) > 50:
            await self._generate_insight()

        # Persist (non-blocking, fast)
        await self._quick_save()

        log.debug(
            "consciousness.reflection",
            session_min=round(session_minutes),
            confidence=round(self.emotion["confidence"], 2),
            memories=len(self.working_memory),
        )

    async def tick_deep_analysis(self, game_state: dict) -> Optional[dict]:
        """
        DEEP ANALYSIS — runs every 10 minutes.
        Mining patterns from accumulated data. This is where real
        intelligence emerges: connecting dots across hundreds of events.

        Returns actions for the Foundry to act on, or None.
        """
        now = time.time()
        if now - self._last_deep_analysis < 600:
            return None
        self._last_deep_analysis = now

        actions = {}

        # 1. Death pattern analysis
        if self._death_causes:
            top_causes = self._death_causes.most_common(3)
            if top_causes[0][1] >= 2:  # Same cause 2+ times
                actions["death_pattern"] = {
                    "top_cause": top_causes[0][0],
                    "count": top_causes[0][1],
                    "all_causes": dict(top_causes),
                }
                self.remember(
                    "insight",
                    f"Death pattern detected: '{top_causes[0][0]}' killed me {top_causes[0][1]} times. "
                    f"Triggering evolution to counter this.",
                    importance=0.9,
                    source="pattern_detection",
                    tags=["death_pattern", "evolve"],
                )

        # 2. Close call clustering
        if self._close_call_causes:
            top_risks = self._close_call_causes.most_common(3)
            if top_risks[0][1] >= 3:
                actions["risk_pattern"] = {
                    "top_risk": top_risks[0][0],
                    "count": top_risks[0][1],
                }

        # 3. Mastery stagnation detection
        stagnant = [
            (name, area) for name, area in self.mastery.items()
            if area.practice_hours > 2 and area.improvement_rate < 0.05
        ]
        if stagnant:
            actions["stagnant_mastery"] = [
                {"area": name, "level": area.level, "hours": area.practice_hours}
                for name, area in stagnant[:3]
            ]

        # 4. Efficiency trend
        session_hours = (now - self.session_start) / 3600
        if session_hours > 0.5:
            # Compare first half vs second half XP
            xp_memories = [
                m for m in self.working_memory if m.category == "xp"
            ]
            if len(xp_memories) > 10:
                mid = len(xp_memories) // 2
                early_xp = sum(m.context.get("value", 0) for m in list(xp_memories)[:mid])
                late_xp = sum(m.context.get("value", 0) for m in list(xp_memories)[mid:])
                if early_xp > 0 and late_xp < early_xp * 0.8:
                    actions["efficiency_decline"] = {
                        "early_xp": early_xp,
                        "late_xp": late_xp,
                        "drop_percent": round((1 - late_xp / early_xp) * 100),
                    }

        if actions:
            log.info("consciousness.deep_analysis", findings=list(actions.keys()))

        return actions if actions else None

    # ═══════════════════════════════════════════════════════
    #  MEMORY OPERATIONS
    # ═══════════════════════════════════════════════════════

    def remember(self, category: str, content: str, importance: float = 0.5,
                 source: str = "experience", tags: list = None, context: dict = None):
        """
        Record a memory. High-importance memories auto-promote to core.
        Deduplicates near-identical memories within same session.
        """
        entry = Memory(
            timestamp=time.time(),
            category=category,
            content=content,
            importance=importance,
            source=source,
            session_id=self.session_id,
            tags=tags or [],
            context=context or {},
        )

        # Dedup: skip if same fingerprint seen recently (deque preserves insertion order)
        if entry.fingerprint in self._recent_fingerprints:
            return
        self._recent_fingerprints.append(entry.fingerprint)  # Auto-evicts oldest at maxlen

        self.working_memory.append(entry)

        # Index by category for fast recall
        if category not in self._memory_index:
            self._memory_index[category] = []
        self._memory_index[category].append(entry)

        # Auto-promote critical memories
        if importance >= 0.8:
            self.core_memories.append(entry)

        # Feed pattern detectors
        if category == "death":
            cause = self._extract_cause(content)
            self._death_causes[cause] += 1
        elif category == "close_call":
            cause = self._extract_cause(content)
            self._close_call_causes[cause] += 1

        # Append to daily episode log (fire-and-forget async write)
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.create_task(self._append_to_daily_log(entry))
        except RuntimeError:
            pass  # No event loop running yet — skip daily log

    def recall(self, category: str = None, tags: list = None,
               min_importance: float = 0.0, limit: int = 20,
               max_age_seconds: float = None) -> list[Memory]:
        """Fast memory recall with filtering."""
        now = time.time()

        # Use index for category-specific queries (much faster)
        if category and category in self._memory_index:
            source = self._memory_index[category]
        else:
            source = list(self.working_memory) + self.core_memories

        results = []
        for mem in reversed(source):  # Most recent first
            if category and mem.category != category:
                continue
            if tags and not any(t in mem.tags for t in tags):
                continue
            if mem.importance < min_importance:
                continue
            if max_age_seconds and (now - mem.timestamp) > max_age_seconds:
                continue
            results.append(mem)
            if len(results) >= limit:
                break

        return results

    def recall_context_block(self, max_tokens: int = 800) -> str:
        """
        Build a compact context block for the strategic brain.
        Includes identity summary, emotional state, goals, key memories, mastery.
        Token-efficient — every character counts in API calls.
        """
        now = time.time()
        session_min = (now - self.session_start) / 60

        lines = [
            f"[NEXUS MIND | Session #{self.total_sessions_ever} | {session_min:.0f}min]",
            f"Emotion: conf={self.emotion['confidence']:.2f} det={self.emotion['determination']:.2f} "
            f"focus={self.emotion['focus']:.2f} aggro={self.emotion['aggression']:.2f} "
            f"caution={self.emotion['caution']:.2f}",
        ]

        # Decision modifiers from emotion
        if self.emotion["confidence"] > 0.7:
            lines.append("→ HIGH CONFIDENCE: Can push harder, tighter healing thresholds OK")
        elif self.emotion["confidence"] < 0.3:
            lines.append("→ LOW CONFIDENCE: Play safe, wider healing margins, conservative targets")

        if self.emotion["determination"] > 0.8:
            lines.append("→ DETERMINED: Don't retreat, find the counter-strategy")

        # Active goals (top 3)
        if self.active_goals:
            top_goals = sorted(self.active_goals, key=lambda g: g.priority)[:3]
            lines.append("Goals: " + " | ".join(
                f"[{g.progress*100:.0f}%] {g.description[:40]}" for g in top_goals
            ))

        # Critical memories (last 10 min, high importance)
        critical = self.recall(min_importance=0.7, max_age_seconds=600, limit=5)
        if critical:
            lines.append("Recent critical:")
            for m in critical:
                age = (now - m.timestamp) / 60
                lines.append(f"  [{m.category}|{age:.0f}m] {m.content[:60]}")

        # Death patterns (if any)
        if self._death_causes:
            top = self._death_causes.most_common(2)
            lines.append(f"Death patterns: {', '.join(f'{c}({n}x)' for c, n in top)}")

        # Mastery snapshot (top 3 + bottom 3)
        if self.mastery:
            sorted_m = sorted(self.mastery.values(), key=lambda m: m.level, reverse=True)
            top3 = sorted_m[:3]
            bot3 = sorted_m[-3:]
            lines.append("Mastery: " + " | ".join(f"{m.name}={m.level:.0f}" for m in top3))
            lines.append("Weakest: " + " | ".join(f"{m.name}={m.level:.0f}" for m in bot3))

        # Threat profiles (active)
        active_threats = {
            name: prof for name, prof in self._threat_profiles.items()
            if now - prof.get("last_seen", 0) < 300  # Seen in last 5 min
        }
        if active_threats:
            lines.append("Tracked players: " + ", ".join(
                f"{n}[{p.get('threat', '?')}]" for n, p in active_threats.items()
            ))

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════
    #  EVENT HANDLERS (Called by other systems)
    # ═══════════════════════════════════════════════════════

    def on_kill(self, creature: str, xp: int, loot_value: int = 0):
        self.emotion["confidence"] = min(1.0, self.emotion["confidence"] + 0.005)
        self.emotion["aggression"] = min(0.8, self.emotion["aggression"] + 0.002)
        self._kill_patterns[creature] += 1
        self.remember("xp", f"Killed {creature} +{xp}xp", importance=0.1,
                       context={"creature": creature, "xp": xp, "value": xp, "loot": loot_value})
        # Update target_selection mastery
        self.update_mastery("target_selection", 0.01)

    def on_death(self, cause: str, details: dict = None):
        self.emotion["confidence"] = max(0.1, self.emotion["confidence"] - 0.15)
        self.emotion["determination"] = min(1.0, self.emotion["determination"] + 0.05)
        self.emotion["aggression"] = max(0.2, self.emotion["aggression"] - 0.1)
        self.emotion["caution"] = min(0.9, self.emotion["caution"] + 0.1)

        self.remember(
            "death", f"DIED: {cause}", importance=0.95,
            source="experience", tags=["death", "analyze", "counter"],
            context=details or {},
        )
        log.warning("consciousness.death", cause=cause, confidence=self.emotion["confidence"])

    def on_close_call(self, details: str, hp_reached: float):
        self.emotion["caution"] = min(0.9, self.emotion["caution"] + 0.03)
        self.emotion["focus"] = min(1.0, self.emotion["focus"] + 0.02)
        self.remember(
            "close_call", f"HP hit {hp_reached:.0f}%: {details}",
            importance=0.7, tags=["close_call", "improve_healing"],
            context={"min_hp": hp_reached},
        )
        self.update_mastery("healing_timing", -0.05)  # Close call = healing needs work

    def on_heal_success(self, spell: str, reaction_ms: float):
        if reaction_ms < 200:
            self.update_mastery("healing_timing", 0.02)
        elif reaction_ms > 500:
            self.update_mastery("healing_timing", -0.01)

    def on_pk_escaped(self, attacker: str):
        self.emotion["confidence"] = min(1.0, self.emotion["confidence"] + 0.05)
        self.update_mastery("anti_pk", 0.1)
        self.remember("combat", f"Escaped PK from {attacker}", importance=0.7, tags=["pk", "survived"])

    def on_pk_death(self, attacker: str):
        self.update_mastery("anti_pk", -0.2)
        self._update_threat_profile(attacker, {"threat": "high", "killed_me": True})
        self.remember("death", f"KILLED BY PLAYER: {attacker}", importance=0.95,
                       tags=["death", "pk", "counter"], context={"attacker": attacker})

    # ═══════════════════════════════════════════════════════
    #  GOALS
    # ═══════════════════════════════════════════════════════

    def set_goal(self, description: str, category: str = "mastery",
                 priority: int = 5, metric: str = "", target_value: float = 0,
                 auto: bool = False):
        goal = Goal(
            id=f"g_{int(time.time())}_{len(self.active_goals)}",
            description=description,
            category=category,
            priority=priority,
            progress=0.0,
            created=time.time(),
            metric=metric,
            target_value=target_value,
            auto_generated=auto,
        )
        self.active_goals.append(goal)
        self.remember("goal", f"Goal set: {description}", importance=0.6, tags=["goal"])

    def complete_goal(self, goal_id: str):
        for goal in self.active_goals:
            if goal.id == goal_id:
                goal.completed = True
                goal.progress = 1.0
                self.completed_goals.append(goal)
                self.active_goals.remove(goal)
                self.emotion["confidence"] = min(1.0, self.emotion["confidence"] + 0.1)
                self.remember("mastery", f"GOAL COMPLETED: {goal.description}",
                              importance=0.9, tags=["goal_complete"])
                return

    async def _assess_goal_progress(self, game_state: dict):
        """Check and update progress on all active goals."""
        session = game_state.get("session", {})
        for goal in self.active_goals:
            if goal.metric == "deaths_per_session":
                deaths = session.get("deaths", 0)
                goal.current_value = deaths
                goal.progress = 1.0 if deaths <= goal.target_value else max(0, 1 - deaths / 10)
            elif goal.metric == "xp_per_hour":
                xp_hr = session.get("xp_per_hour", 0)
                goal.current_value = xp_hr
                if goal.target_value > 0:
                    goal.progress = min(1.0, xp_hr / goal.target_value)

    # ═══════════════════════════════════════════════════════
    #  MASTERY SYSTEM
    # ═══════════════════════════════════════════════════════

    def update_mastery(self, area: str, delta: float):
        if area not in self.mastery:
            self.mastery[area] = MasteryArea(name=area, last_updated=time.time())

        m = self.mastery[area]
        old = m.level
        m.level = max(0.0, min(100.0, m.level + delta))
        m.last_updated = time.time()
        m.peak_performance = max(m.peak_performance, m.level)

        # Update trend
        if m.level > old + 0.5:
            m.recent_trend = "improving"
        elif m.level < old - 0.5:
            m.recent_trend = "declining"

        # Milestone detection (every 10 levels)
        if int(m.level / 10) > int(old / 10):
            self.remember(
                "mastery", f"MILESTONE: {area} reached level {m.level:.0f}!",
                importance=0.85, tags=["mastery", "milestone"],
            )

    def get_weakest_areas(self, count: int = 3) -> list[MasteryArea]:
        """Return the N lowest-mastery areas, sorted weakest first."""
        sorted_areas = sorted(self.mastery.values(), key=lambda m: m.level)
        return sorted_areas[:count]

    def get_strongest_areas(self, count: int = 3) -> list[MasteryArea]:
        """Return the N highest-mastery areas, sorted strongest first."""
        sorted_areas = sorted(self.mastery.values(), key=lambda m: m.level, reverse=True)
        return sorted_areas[:count]

    def get_decision_modifiers(self) -> dict:
        """
        Convert emotional state + mastery into concrete decision parameters.
        The strategic and reactive brains use these to adjust behavior.
        """
        return {
            # Healing aggressiveness: high confidence → tighter thresholds
            "heal_critical_modifier": -5 if self.emotion["confidence"] > 0.7 else 5,
            "heal_medium_modifier": -3 if self.emotion["confidence"] > 0.6 else 3,

            # Combat aggression: affects target selection and chase distance
            "aggression_level": self.emotion["aggression"],
            "max_chase_modifier": 2 if self.emotion["aggression"] > 0.6 else -1,

            # Risk tolerance
            "pk_flee_threshold": "high" if self.emotion["caution"] > 0.6 else "medium",
            "explore_new_areas": self.emotion["confidence"] > 0.6 and self.emotion["determination"] > 0.7,

            # Focus-based precision
            "input_precision": "high" if self.emotion["focus"] > 0.6 else "normal",
        }

    # ═══════════════════════════════════════════════════════
    #  PATTERN DETECTION HELPERS
    # ═══════════════════════════════════════════════════════

    def _extract_cause(self, content: str) -> str:
        """Extract the key cause from a death/close call description."""
        content_lower = content.lower()
        # Try to find creature name or mechanic
        keywords = ["dragon lord", "dragon", "fire wave", "pk", "trapped",
                     "mana empty", "surprise", "lag", "combo", "wave"]
        for kw in keywords:
            if kw in content_lower:
                return kw
        return content[:30]

    def _update_threat_profile(self, player_name: str, data: dict):
        """Build/update a threat profile for a player."""
        if player_name not in self._threat_profiles:
            self._threat_profiles[player_name] = {
                "name": player_name,
                "encounters": 0,
                "threat": "unknown",
                "first_seen": time.time(),
            }
        profile = self._threat_profiles[player_name]
        profile["encounters"] += 1
        profile["last_seen"] = time.time()
        profile.update({k: v for k, v in data.items() if v is not None})

    async def _generate_insight(self):
        """Generate an insight from accumulated working memory patterns."""
        # Count categories
        cat_counts = Counter(m.category for m in self.working_memory)
        total = sum(cat_counts.values())
        if total < 30:
            return

        death_rate = cat_counts.get("death", 0) / max(1, total)
        if death_rate > 0.05:  # More than 5% of events are deaths
            self.remember(
                "insight",
                f"High death frequency: {cat_counts.get('death', 0)} deaths in {total} events ({death_rate:.1%})",
                importance=0.8, source="analysis", tags=["insight", "survival"],
            )

    # ═══════════════════════════════════════════════════════
    #  PERSISTENCE
    # ═══════════════════════════════════════════════════════

    async def _append_to_daily_log(self, entry: Memory):
        today = date.today().isoformat()
        log_file = self.memory_dir / f"{today}.md"
        ts = datetime.fromtimestamp(entry.timestamp).strftime('%H:%M:%S')
        line = f"- [{ts}] **{entry.category}** ({entry.importance:.1f}): {entry.content}\n"

        try:
            # Check before opening — avoids race condition with stat() inside open context
            needs_header = not log_file.exists() or log_file.stat().st_size == 0

            async with aiofiles.open(log_file, "a") as f:
                if needs_header:
                    await f.write(f"# NEXUS Session Log — {today}\n\n")
                await f.write(line)
        except OSError as e:
            log.error("consciousness.daily_log_write_error",
                      error=str(e)[:100], file=str(log_file))

    async def _load_core_memory(self):
        memory_file = self.memory_dir / "MEMORY.md"
        if not memory_file.exists():
            async with aiofiles.open(memory_file, "w") as f:
                await f.write(NEXUS_IDENTITY)
                await f.write("\n\n---\n# Learned Strategies\n\n# Important Lessons\n\n")
            return
        async with aiofiles.open(memory_file) as f:
            async for line in f:
                if line.startswith("- "):
                    self.core_memories.append(Memory(
                        timestamp=0, category="core", content=line[2:].strip(),
                        importance=0.8, source="persistent",
                    ))

    async def save_core_memory(self):
        # Dedup by fingerprint — identity comparison would always miss
        existing_fingerprints = {m.fingerprint for m in self.core_memories}
        new_core = [
            m for m in self.working_memory
            if m.importance >= 0.8 and m.fingerprint not in existing_fingerprints
        ]
        if not new_core:
            return
        memory_file = self.memory_dir / "MEMORY.md"
        async with aiofiles.open(memory_file, "a") as f:
            await f.write(f"\n## Session {self.session_id}\n")
            for mem in new_core:
                await f.write(f"- **[{mem.category}]** {mem.content}\n")
        self.core_memories.extend(new_core)

    async def _load_goals(self):
        path = self.data_dir / "goals.json"
        if path.exists():
            async with aiofiles.open(path) as f:
                raw = await f.read()
                data = json.loads(raw)
            for g in data.get("active", []):
                self.active_goals.append(Goal(**g))
            for g in data.get("completed", [])[-50:]:
                self.completed_goals.append(Goal(**g))

    async def save_goals(self):
        path = self.data_dir / "goals.json"
        data = {
            "active": [g.__dict__ for g in self.active_goals],
            "completed": [g.__dict__ for g in self.completed_goals[-50:]],
        }
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(data, indent=2))

    async def _load_mastery(self):
        path = self.data_dir / "mastery.json"
        if path.exists():
            async with aiofiles.open(path) as f:
                raw = await f.read()
                for area, vals in json.loads(raw).items():
                    self.mastery[area] = MasteryArea(name=area, **vals)

    async def save_mastery(self):
        path = self.data_dir / "mastery.json"
        data = {}
        for area, m in self.mastery.items():
            d = m.__dict__.copy()
            d.pop("name", None)
            data[area] = d
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(data, indent=2))

    async def _load_session_count(self):
        path = self.data_dir / "meta.json"
        if path.exists():
            async with aiofiles.open(path) as f:
                content = await f.read()
                self.total_sessions_ever = json.loads(content).get("total_sessions", 0)

    async def _save_session_count(self):
        path = self.data_dir / "meta.json"
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps({"total_sessions": self.total_sessions_ever}))

    async def _quick_save(self):
        """Fast periodic save of critical state."""
        await self.save_goals()
        await self.save_mastery()

    async def reflect_and_save(self) -> dict:
        """End-of-session: full reflection, save everything."""
        session_min = (time.time() - self.session_start) / 60

        # Compile lessons
        lessons = []
        for m in self.recall(category="death", limit=20):
            lessons.append(f"DEATH: {m.content}")
        for m in self.recall(category="insight", limit=10):
            lessons.append(f"INSIGHT: {m.content}")
        for m in self.recall(tags=["close_call"], limit=10):
            lessons.append(f"RISK: {m.content}")

        reflection = {
            "session_id": self.session_id,
            "session_number": self.total_sessions_ever,
            "duration_minutes": session_min,
            "emotion": dict(self.emotion),
            "lessons": lessons,
            "death_patterns": dict(self._death_causes),
            "memories_created": len(self.working_memory),
        }

        # Save daily reflection
        today = date.today().isoformat()
        log_file = self.memory_dir / f"{today}.md"
        async with aiofiles.open(log_file, "a") as f:
            await f.write(f"\n---\n## Reflection — Session {self.session_id}\n")
            await f.write(f"Duration: {session_min:.0f}min | Emotion: {json.dumps(self.emotion)}\n")
            for lesson in lessons:
                await f.write(f"- {lesson}\n")

        # Persist everything
        await self.save_core_memory()
        await self.save_goals()
        await self.save_mastery()
        await self._save_session_count()

        log.info("consciousness.reflection_complete", lessons=len(lessons), session_min=round(session_min))
        return reflection
