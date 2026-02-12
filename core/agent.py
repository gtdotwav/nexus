"""
NEXUS Agent — Main Orchestrator

Not just a bot orchestrator. This is the LIFE CYCLE of an autonomous intelligence.

Inspired by OpenClaw's architecture:
- Always-on consciousness with multi-frequency awareness (never sleeps)
- Foundry for self-evolution (creates and improves its own skills)
- Emotional dynamics that directly affect decision parameters
- Goal system with determination, progress tracking, and mastery

The agent THINKS, LEARNS, REMEMBERS, and EVOLVES across sessions.
The player controls start/stop. NEXUS never decides to pause itself.

ARCHITECTURE NOTE:
    All 9 loops are in core/loops/ as separate files.
    Each loop is: async def run(agent: NexusAgent) -> None
    To add a new loop, create core/loops/my_loop.py and register it here.
"""

from __future__ import annotations

import asyncio
import signal
import time
import yaml
import structlog
from pathlib import Path

from core.state import GameState, AgentMode
from core.consciousness import Consciousness
from core.foundry import Foundry
from core.recovery import DeathRecovery
from core.event_bus import EventBus, EventType
from core.loops import ALL_LOOPS
from perception.screen_capture import ScreenCapture
from perception.game_reader_v2 import GameReaderV2
from brain.reactive import ReactiveBrain
from brain.strategic import StrategicBrain
from skills.engine import SkillEngine
from actions.navigator import Navigator
from actions.looting import LootEngine
from actions.supply_manager import SupplyManager
from actions.behaviors import BehaviorEngine
from actions.explorer import Explorer, ExploreStrategy
from perception.spatial_memory_v2 import SpatialMemoryV2
from brain.reasoning import ReasoningEngine

log = structlog.get_logger()


class NexusAgent:
    """
    Main agent class. Orchestrates all subsystems.

    Lifecycle:
        1. AWAKEN — Load consciousness (identity, memories, goals, mastery)
        1.5 REMEMBER — Load spatial memory (persistent world map)
        2. PERCEIVE — Calibrate perception (find game window)
        3. PREPARE — Load skills, configure subsystems, select best skill
        4. LIVE — Run all loops concurrently (see core/loops/)
        5. REFLECT — End-of-session analysis, save memories, save maps, evolve skills
        6. SLEEP — Persist everything to disk for next session
    """

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = self._load_config(config_path)
        self.state = GameState()
        self.running = False
        self._tasks: list[asyncio.Task] = []

        # === EVENT BUS (decoupled communication) ===
        self.event_bus = EventBus(history_size=200)

        # === CONSCIOUSNESS (the soul) ===
        self.consciousness = Consciousness(data_dir="data")

        # === PERCEPTION (the eyes) ===
        # v2: pixel analysis in thread pool, no EasyOCR, <2ms per frame
        self.screen_capture = ScreenCapture(self.config["perception"])
        self.game_reader = GameReaderV2(self.state, self.config["perception"])

        # === BRAINS (instinct + intelligence) ===
        # v3: singleton pynput controllers, 0ms overhead per input
        self.reactive_brain = ReactiveBrain(self.state, self.config["reactive"], self.config["input"])
        # v2: state-diff skip saves ~30% API calls
        self.strategic_brain = StrategicBrain(self.state, self.config["ai"])

        # === SKILLS (capabilities) ===
        self.skill_engine = SkillEngine(self.state, self.config["skills"], self.strategic_brain)

        # === ACTION SYSTEMS (the hands) ===
        self.navigator = Navigator(
            self.state, self.reactive_brain.input,
            self.config.get("navigation", {}),
        )
        self.loot_engine = LootEngine(
            self.state, self.reactive_brain.input,
            self.config.get("perception", {}),
        )
        self.supply_manager = SupplyManager(self.state, self.config.get("reactive", {}))
        self.behavior_engine = BehaviorEngine(
            self.state, self.reactive_brain.input,
            self.config.get("input", {}),
        )

        # === RECOVERY (the resilience) ===
        self.recovery = DeathRecovery(
            self.state, self.reactive_brain.input,
            self.config.get("reactive", {}),
        )

        # === SPATIAL MEMORY (persistent world map — SQLite backend) ===
        # v2: SQLite + WAL mode, O(1) writes, O(log n) spatial queries
        self.spatial_memory = SpatialMemoryV2(data_dir="data")

        # === REASONING ENGINE (local real-time inference) ===
        self.reasoning_engine = ReasoningEngine(self.state, self.spatial_memory)

        # === EXPLORER (autonomous territory discovery) ===
        self.explorer = Explorer(
            self.state, self.spatial_memory, self.navigator,
            self.config.get("exploration", {}),
        )

        # === FOUNDRY (self-evolution engine) ===
        self.foundry = Foundry(self.consciousness, self.strategic_brain, self.skill_engine)

        # === WIRING (connect all subsystems) ===
        self.strategic_brain.consciousness = self.consciousness
        self.strategic_brain.spatial_memory = self.spatial_memory
        self.strategic_brain.reasoning_engine = self.reasoning_engine
        self.reactive_brain.consciousness = self.consciousness
        self.foundry.reactive_brain = self.reactive_brain

        # Wire state events → consciousness + event bus
        self._wire_consciousness_events()
        self._wire_event_bus()

        log.info("nexus.initialized", game=self.config["agent"]["game"],
                 event_bus=True, perception="v2_pixel", spatial="sqlite")

    def _load_config(self, path: str) -> dict:
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(config_path) as f:
            return yaml.safe_load(f)

    # ═══════════════════════════════════════════════════════
    #  LIFECYCLE
    # ═══════════════════════════════════════════════════════

    async def start(self):
        """Start all agent systems — the agent AWAKENS."""
        self.running = True
        self.state.session.start_time = time.time()

        log.info("nexus.awakening", character=self.config["agent"].get("character_name", "Unknown"))

        # Phase 1: AWAKEN — Load consciousness
        log.info("nexus.loading_consciousness")
        await self.consciousness.initialize()
        await self.foundry.initialize()

        # Set initial goals if first session
        if not self.consciousness.active_goals:
            self.consciousness.set_goal("Master current hunting ground — reach 90+ skill score", "mastery", 1)
            self.consciousness.set_goal("Achieve 0 deaths in a full session", "survival", 2)
            self.consciousness.set_goal("Optimize XP/hr to maximum for current level", "farming", 3)

        # Phase 1.5: REMEMBER — Load spatial memory (persistent world map)
        log.info("nexus.loading_spatial_memory")
        await self.spatial_memory.initialize()

        # Phase 2: PERCEIVE — Calibrate perception
        log.info("nexus.calibrating", phase="perception")
        await self.screen_capture.initialize()
        await self.game_reader.calibrate()

        # Phase 3: PREPARE — Load skills and configure subsystems
        log.info("nexus.loading_skills")
        await self.skill_engine.load_skills()
        active_skill = self.skill_engine.get_best_skill_for_current_context()
        if active_skill:
            self._activate_skill(active_skill)
            self.consciousness.remember(
                "strategy", f"Session started with skill: {active_skill.name}",
                importance=0.5, tags=["session_start"],
            )

        # Phase 4: LIVE — Start all loops from core/loops/ package
        log.info("nexus.starting_loops", count=len(ALL_LOOPS))

        # Set event loop for thread-safe perception events
        self.event_bus.set_loop(asyncio.get_event_loop())

        # Emit agent started event
        await self.event_bus.emit(EventType.AGENT_STARTED, {
            "config": self.config.get("agent", {}),
            "goals": len(self.consciousness.active_goals),
        }, source="agent")

        # Register all loops from the loops package
        self._tasks = [
            asyncio.create_task(loop_fn(self), name=name)
            for name, loop_fn in ALL_LOOPS
        ]

        self.state.set_mode(AgentMode.HUNTING)
        log.info("nexus.alive", mode="HUNTING",
                 goals=len(self.consciousness.active_goals),
                 loops=len(self._tasks))

        # Wait for all tasks (they run forever until shutdown)
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            log.info("nexus.shutdown_requested")

    async def stop(self):
        """Gracefully stop — the agent REFLECTS and SLEEPS."""
        log.info("nexus.reflecting")
        self.running = False

        await self.event_bus.emit(EventType.AGENT_STOPPING, source="agent")

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Phase 5: REFLECT — End-of-session analysis
        reflection = await self.consciousness.reflect_and_save()

        # Save spatial memory (persistent world map)
        await self.spatial_memory.save()

        # Stop exploration if active
        if self.explorer.active:
            findings = self.explorer.stop_exploration()
            skill_data = self.explorer.generate_skill_from_exploration()
            if skill_data:
                await self.skill_engine.save_skill_from_data(skill_data)

        # Discover zones from accumulated spatial data
        for z in self.spatial_memory.floors:
            self.spatial_memory.discover_zones(z)

        # Run improvement cycle on all skills
        await self.skill_engine.run_improvement_cycle()

        # Final session report
        snapshot = self.state.get_snapshot()
        log.info(
            "nexus.session_complete",
            duration_min=snapshot["session"]["duration_minutes"],
            xp_per_hour=snapshot["session"]["xp_per_hour"],
            profit_per_hour=snapshot["session"]["profit_per_hour"],
            deaths=snapshot["session"]["deaths"],
            kills=snapshot["session"]["kills"],
            lessons_learned=len(reflection.get("lessons", [])),
            mastery_areas=len(self.consciousness.mastery),
            total_evolutions=self.foundry.total_evolutions,
            navigator=self.navigator.stats,
            loot=self.loot_engine.stats,
            supply_runs=self.supply_manager.depot_runs,
            recoveries=self.recovery.total_recoveries,
            spatial_memory=self.spatial_memory.stats,
            reasoning=self.reasoning_engine.stats,
            explorer=self.explorer.stats,
        )

    def _activate_skill(self, skill):
        """Activate a skill and configure all subsystems from it."""
        self.state.active_skill = skill.name
        log.info("nexus.skill_activated", skill=skill.name)

        # Load waypoints into navigator
        if skill.waypoints:
            escape_wps = skill.anti_pk.get("escape_waypoints", []) if skill.anti_pk else []
            self.navigator.load_route(skill.waypoints, escape_wps)

        # Load loot config
        loot_config = getattr(skill, "metadata", {}).get("loot", {})
        # Try top-level loot field first (from YAML)
        if hasattr(skill, "_raw_data") and "loot" in skill._raw_data:
            loot_config = skill._raw_data["loot"]
        self.loot_engine.load_loot_config(loot_config)

        # Load supply config
        if skill.supplies:
            self.supply_manager.load_supply_config(skill.supplies)

        # Load behaviors
        behaviors_config = getattr(skill, "metadata", {}).get("behaviors", {})
        if hasattr(skill, "_raw_data") and "behaviors" in skill._raw_data:
            behaviors_config = skill._raw_data["behaviors"]
        hotkeys = self.config["reactive"].get("hotkeys", {})
        self.behavior_engine.load_behaviors(behaviors_config, hotkeys)

    # ═══════════════════════════════════════════════════════
    #  EVENT WIRING
    # ═══════════════════════════════════════════════════════

    def _wire_consciousness_events(self):
        """
        Connect game state events to consciousness handlers.
        Gives consciousness real-time awareness of everything in-game.
        """
        def on_hp_changed(data):
            new_hp = data.get("new", 100)
            old_hp = data.get("old", 100)
            if new_hp < 25 and old_hp >= 25:
                self.consciousness.on_close_call(
                    f"HP dropped from {old_hp:.0f}% to {new_hp:.0f}%",
                    hp_reached=new_hp,
                )
            # Record damage in spatial memory
            if new_hp < old_hp:
                pos = self.state.position
                if pos:
                    damage_pct = old_hp - new_hp
                    self.spatial_memory.observe_damage(
                        pos.x, pos.y, pos.z, damage_pct)

        def on_mode_changed(data):
            new_mode = data.get("new")
            if new_mode == AgentMode.FLEEING:
                self.consciousness.remember(
                    "combat", "Entered FLEEING mode — threat detected",
                    importance=0.6, tags=["flee", "threat"],
                )

        def on_kill(data):
            creature = data.get("creature", "unknown")
            xp = data.get("value", 0)
            self.consciousness.on_kill(creature, xp)

        def on_death(data):
            cause = data.get("cause", "unknown")
            self.consciousness.on_death(cause, details=data)
            # Record death in spatial memory
            pos = self.state.position
            if pos:
                self.spatial_memory.observe_death(pos.x, pos.y, pos.z, cause)
            # Notify explorer if active
            if self.explorer.active:
                self.explorer.record_death(cause)

        self.state.on("hp_changed", on_hp_changed)
        self.state.on("mode_changed", on_mode_changed)
        self.state.on("kill", on_kill)
        self.state.on("death", on_death)

    def _wire_event_bus(self):
        """
        Wire state events into the event bus for decoupled communication.
        This allows new components (dashboard, plugins, game adapters)
        to subscribe to events without modifying existing code.
        """
        bus = self.event_bus

        # Bridge GameState events → EventBus
        def bridge_hp(data):
            bus.emit_threadsafe(EventType.HP_CHANGED, data, source="state")

        def bridge_mode(data):
            bus.emit_threadsafe(EventType.MODE_CHANGED, {
                "old": data.get("old", "").name if hasattr(data.get("old", ""), "name") else str(data.get("old", "")),
                "new": data.get("new", "").name if hasattr(data.get("new", ""), "name") else str(data.get("new", "")),
            }, source="state")

        def bridge_kill(data):
            bus.emit_threadsafe(EventType.KILL, data, source="state")

        def bridge_death(data):
            bus.emit_threadsafe(EventType.DEATH, data, source="state")

        def bridge_battle(data):
            bus.emit_threadsafe(EventType.STATE_UPDATED, {
                "component": "battle_list",
            }, source="state")

        self.state.on("hp_changed", bridge_hp)
        self.state.on("mode_changed", bridge_mode)
        self.state.on("kill", bridge_kill)
        self.state.on("death", bridge_death)
        self.state.on("battle_list_changed", bridge_battle)


async def main():
    """Entry point for the NEXUS agent."""
    agent = NexusAgent()

    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(agent.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: signal_handler())

    try:
        await agent.start()
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
