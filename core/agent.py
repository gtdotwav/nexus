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
        4. LIVE — Run all loops concurrently (9 concurrent):
           - Perception (30fps) → sees the game + feeds spatial memory
           - Reactive brain (40 ticks/s) → instinctive survival + combat
           - Action loop (10 ticks/s) → navigation, loot, supplies, behaviors, exploration
           - Strategic brain (every 3s) → deep thinking via Claude (now exploration-aware)
           - Consciousness (always-on, multi-frequency):
               • Instinct every 1s → emotional micro-ticks
               • Awareness every 10s → pattern recognition
               • Reflection every 2min → strategy assessment
               • Deep analysis every 10min → evolution triggers
           - Foundry evolution (continuous) → self-improvement experiments
           - Recovery system → death detection and autonomous recovery
           - Reasoning loop (every 2.5s) → local real-time inference on spatial data
           - Metrics tracking (every 60s) → performance monitoring
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

        # Phase 4: LIVE — Start all loops
        log.info("nexus.starting_loops")

        # Set event loop for thread-safe perception events
        self.event_bus.set_loop(asyncio.get_event_loop())

        # Emit agent started event
        await self.event_bus.emit(EventType.AGENT_STARTED, {
            "config": self.config.get("agent", {}),
            "goals": len(self.consciousness.active_goals),
        }, source="agent")

        self._tasks = [
            asyncio.create_task(self._perception_loop(), name="perception"),
            asyncio.create_task(self._reactive_loop(), name="reactive"),
            asyncio.create_task(self._action_loop(), name="actions"),
            asyncio.create_task(self._strategic_loop(), name="strategic"),
            asyncio.create_task(self._consciousness_loop(), name="consciousness"),
            asyncio.create_task(self._evolution_loop(), name="evolution"),
            asyncio.create_task(self._recovery_loop(), name="recovery"),
            asyncio.create_task(self._reasoning_loop(), name="reasoning"),
            asyncio.create_task(self._metrics_loop(), name="metrics"),
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
    #  CORE LOOPS
    # ═══════════════════════════════════════════════════════

    async def _perception_loop(self):
        """
        Captures screen and updates game state.
        Runs at configured FPS (default 30fps = ~33ms per frame).
        """
        target_interval = 1.0 / self.config["perception"]["capture"]["fps"]

        while self.running:
            start = time.perf_counter()

            try:
                frame = await self.screen_capture.capture()
                if frame is not None:
                    await self.game_reader.process_frame(frame)
                    self.state.last_perception_update = time.time()

                    # Feed spatial memory with current observations
                    pos = self.state.position
                    if pos:
                        self.spatial_memory.observe_position(pos.x, pos.y, pos.z)

                        # Record creature positions from battle list
                        for creature in self.state.battle_list:
                            self.spatial_memory.observe_creature(
                                creature.name,
                                pos.x, pos.y, pos.z,
                                is_player=creature.is_player,
                            )

            except Exception as e:
                log.error("perception.error", error=str(e))

            elapsed = time.perf_counter() - start
            sleep_time = max(0, target_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _reactive_loop(self):
        """
        Fast decision loop for survival actions.
        Runs every 25ms (40 ticks/second).
        Only handles: healing, anti-PK, combat, mana restore.
        """
        tick_rate = self.config["reactive"]["tick_rate_ms"] / 1000

        while self.running:
            start = time.perf_counter()

            try:
                if (self.state.is_alive
                        and self.state.mode != AgentMode.PAUSED
                        and not self.recovery.recovery_active):
                    await self.reactive_brain.tick()

            except Exception as e:
                log.error("reactive.error", error=str(e))

            elapsed = time.perf_counter() - start
            sleep_time = max(0, tick_rate - elapsed)
            await asyncio.sleep(sleep_time)

    async def _action_loop(self):
        """
        Action execution loop for non-combat actions.
        Runs every 100ms (10 ticks/second).
        Handles: navigation, looting, supply checks, behaviors.
        Lower priority than reactive — only runs when not in combat danger.
        """
        while self.running:
            start = time.perf_counter()

            try:
                if (self.state.is_alive
                        and self.state.mode != AgentMode.PAUSED
                        and not self.recovery.recovery_active):

                    # Supply manager — always monitoring
                    supply_action = await self.supply_manager.tick()
                    if supply_action == "needs_depot":
                        self.state.set_mode(AgentMode.DEPOSITING)
                        await self.supply_manager.start_depot_run()

                    # Navigation — runs when not in immediate combat
                    if self.state.mode in (AgentMode.HUNTING, AgentMode.NAVIGATING,
                                           AgentMode.DEPOSITING, AgentMode.FLEEING):
                        nav_action = await self.navigator.tick()

                        # Handle navigator reaching depot
                        if nav_action == "at_depot" and self.supply_manager.depot_run_active:
                            self.supply_manager.notify_arrived_at_depot()

                    # Explorer — when in exploration mode
                    if self.state.mode == AgentMode.EXPLORING and self.explorer.active:
                        explore_action = await self.explorer.tick()

                        if explore_action == "no_targets":
                            # Exploration complete — generate skill if possible
                            skill_data = self.explorer.generate_skill_from_exploration()
                            findings = self.explorer.stop_exploration()
                            self.consciousness.remember(
                                "exploration",
                                f"Exploration complete: {findings['targets_reached']} targets, "
                                f"{findings['waypoints_generated']} waypoints discovered",
                                importance=0.8,
                                tags=["exploration", "map_discovery"],
                            )
                            if skill_data:
                                log.info("nexus.exploration_skill_generated",
                                         name=skill_data["name"])
                                await self.skill_engine.save_skill_from_data(skill_data)
                            self.state.set_mode(AgentMode.HUNTING)

                    # Looting — only when safe
                    if self.state.mode in (AgentMode.HUNTING, AgentMode.EXPLORING):
                        await self.loot_engine.tick()

                    # Behaviors — food, buffs, pull monsters, positioning
                    if self.state.mode in (AgentMode.HUNTING, AgentMode.NAVIGATING,
                                           AgentMode.EXPLORING):
                        await self.behavior_engine.tick()

            except Exception as e:
                log.error("actions.error", error=str(e))

            elapsed = time.perf_counter() - start
            sleep_time = max(0, 0.1 - elapsed)
            await asyncio.sleep(sleep_time)

    async def _strategic_loop(self):
        """
        Deep thinking loop using Claude API.
        Runs every 3-5 seconds (configurable).
        """
        cycle_time = self.config["ai"]["strategic_cycle_seconds"]

        while self.running:
            try:
                if (self.state.is_alive
                        and self.state.mode != AgentMode.PAUSED
                        and not self.recovery.recovery_active):
                    snapshot = self.state.get_snapshot()
                    decisions = await self.strategic_brain.think(snapshot)
                    if decisions:
                        await self._apply_strategic_decisions(decisions)
                    self.state.last_strategic_update = time.time()

            except Exception as e:
                log.error("strategic.error", error=str(e))

            await asyncio.sleep(cycle_time)

    async def _consciousness_loop(self):
        """
        ALWAYS-ON consciousness — runs at multiple frequencies simultaneously.
        """
        while self.running:
            try:
                snapshot = self.state.get_snapshot()
                char = snapshot.get("character", {})
                game_state = {
                    "hp_percent": char.get("hp_percent", 100),
                    "nearby_players": snapshot.get("combat", {}).get("nearby_players", []),
                    "session": snapshot.get("session", {}),
                    "mode": self.state.mode.name,
                    "recovery_active": self.recovery.recovery_active,
                }

                await self.consciousness.tick_instinct(game_state)
                await self.consciousness.tick_awareness(game_state)
                await self.consciousness.tick_reflection(game_state)

                deep_results = await self.consciousness.tick_deep_analysis(game_state)
                if deep_results:
                    await self.foundry.process_consciousness_findings(deep_results, snapshot)

            except Exception as e:
                log.error("consciousness.error", error=str(e))

            await asyncio.sleep(1)

    async def _evolution_loop(self):
        """Foundry continuous evolution."""
        await asyncio.sleep(180)  # Let data accumulate first

        while self.running:
            try:
                if self.state.is_alive:
                    snapshot = self.state.get_snapshot()
                    await self.foundry.evolution_cycle(snapshot)
            except Exception as e:
                log.error("evolution.error", error=str(e))

            await asyncio.sleep(60)

    async def _recovery_loop(self):
        """
        Death recovery loop.
        Continuously monitors for death and manages the recovery pipeline.
        Runs every 500ms.
        """
        while self.running:
            try:
                action = await self.recovery.tick()

                if action == "death_detected":
                    self.state.set_mode(AgentMode.HEALING_CRITICAL)
                    log.info("recovery.death_handling_started")

                elif action == "respawned":
                    self.state.set_mode(AgentMode.NAVIGATING)
                    # Notify consciousness for learning
                    self.consciousness.remember(
                        "recovery",
                        f"Respawned after death #{self.recovery.total_recoveries}. "
                        f"Consecutive: {self.recovery.consecutive_deaths}",
                        importance=0.6,
                        tags=["death", "recovery"],
                    )

                elif action == "returning_to_hunt":
                    # Resume navigation to hunting area
                    self.navigator.current_index = 0
                    self.state.set_mode(AgentMode.NAVIGATING)

                elif action == "recovery_complete":
                    self.state.set_mode(AgentMode.HUNTING)
                    log.info("recovery.complete_returning_to_hunt")

                    # Check if we should change area (too many consecutive deaths)
                    if self.recovery.should_change_area:
                        self.consciousness.remember(
                            "strategy",
                            f"Died {self.recovery.consecutive_deaths} times consecutively. "
                            "Should consider area change or strategy revision.",
                            importance=0.9,
                            tags=["death_pattern", "area_change"],
                        )

            except Exception as e:
                log.error("recovery.error", error=str(e))

            await asyncio.sleep(0.5)

    async def _reasoning_loop(self):
        """
        Local reasoning loop — real-time inference with zero API latency.
        Runs every 2-3 seconds. Analyzes spatial memory + game state
        and produces actionable inferences for the strategic brain.
        Also feeds observations back to spatial memory (damage, loot, deaths).
        """
        while self.running:
            try:
                if (self.state.is_alive
                        and self.state.mode != AgentMode.PAUSED
                        and not self.recovery.recovery_active):

                    profile = await self.reasoning_engine.analyze()

                    # Auto-trigger exploration if in unknown territory
                    if (profile.topology == "unknown"
                            and self.state.mode == AgentMode.HUNTING
                            and not self.explorer.active
                            and profile.recommended_action == "explore"):
                        log.info("reasoning.auto_explore_trigger",
                                 reason="unknown_topology")
                        self.explorer.start_exploration(
                            ExploreStrategy.SAFE, reason="unknown_territory_detected")
                        self.state.set_mode(AgentMode.EXPLORING)

                    # Auto-retreat if reasoning strongly recommends it
                    if (profile.recommended_action == "retreat"
                            and self.state.mode == AgentMode.EXPLORING
                            and self.explorer.active):
                        log.info("reasoning.auto_retreat",
                                 warnings=profile.warnings)
                        self.explorer.strategy = ExploreStrategy.RETURN

            except Exception as e:
                log.error("reasoning.error", error=str(e))

            await asyncio.sleep(2.5)

    async def _metrics_loop(self):
        """Updates session metrics every 60 seconds."""
        while self.running:
            try:
                elapsed_hours = self.state.session_duration_minutes / 60
                if elapsed_hours > 0:
                    self.state.session.xp_per_hour = self.state.session.xp_gained / elapsed_hours
                    self.state.session.profit_per_hour = self.state.session.loot_value / elapsed_hours

                log.info(
                    "metrics.update",
                    xp_hr=round(self.state.session.xp_per_hour),
                    profit_hr=round(self.state.session.profit_per_hour),
                    deaths=self.state.session.deaths,
                    kills=self.state.session.kills,
                    mode=self.state.mode.name,
                    threat=self.state.threat_level.name,
                    nav=f"WP{self.navigator.current_index}/{len(self.navigator.active_route)}",
                    loot=self.loot_engine.items_looted,
                    depot_runs=self.supply_manager.depot_runs,
                    map_cells=self.spatial_memory.total_cells_explored,
                    map_floors=len(self.spatial_memory.floors),
                    reasoning=self.reasoning_engine.current_profile.recommended_action,
                    exploring=self.explorer.active,
                    perception_ms=self.game_reader.avg_frame_ms,
                    event_bus=self.event_bus.stats,
                    strategic_skipped=self.strategic_brain._skipped_calls,
                )
            except Exception as e:
                log.error("metrics.error", error=str(e))

            await asyncio.sleep(60)

    # ═══════════════════════════════════════════════════════
    #  STRATEGIC DECISION APPLICATION
    # ═══════════════════════════════════════════════════════

    async def _apply_strategic_decisions(self, decisions: dict):
        """Apply decisions from strategic brain to all subsystems."""

        if "change_mode" in decisions:
            new_mode = AgentMode[decisions["change_mode"]]
            self.state.set_mode(new_mode)
            log.info("strategic.mode_change", new_mode=new_mode.name)

            # If fleeing, activate escape route
            if new_mode == AgentMode.FLEEING:
                self.navigator.start_escape()
            elif self.navigator.is_escaping:
                self.navigator.stop_escape()

        if "adjust_healing" in decisions:
            self.reactive_brain.update_healing_thresholds(decisions["adjust_healing"])

        if "adjust_aggression" in decisions:
            aggro = decisions["adjust_aggression"]
            self.reactive_brain.update_aggression(aggro)
            log.info("strategic.aggression_adjusted", settings=aggro)

        if "spell_rotation_override" in decisions:
            rotation = decisions["spell_rotation_override"]
            self.reactive_brain.set_spell_rotation(rotation)
            log.info("strategic.rotation_override", rotation=rotation)

        if "reposition" in decisions:
            repo = decisions["reposition"]
            direction = repo.get("direction", "")
            self.reactive_brain.set_reposition_target(direction)

        if "change_target" in decisions:
            target_name = decisions["change_target"]
            for creature in self.state.battle_list:
                if creature.name == target_name:
                    self.state.current_target = creature
                    break

        if "change_skill" in decisions:
            new_skill_name = decisions["change_skill"]
            loaded = await self.skill_engine.activate_skill(new_skill_name)
            if loaded:
                skill = self.skill_engine.skills[new_skill_name]
                self._activate_skill(skill)

        if "create_skill" in decisions:
            skill_request = decisions["create_skill"]
            log.info("strategic.creating_skill", request=skill_request)
            self.state.set_mode(AgentMode.CREATING_SKILL)
            new_skill = await self.skill_engine.create_skill(skill_request)
            if new_skill:
                self._activate_skill(new_skill)
            self.state.set_mode(AgentMode.HUNTING)

        if "return_to_depot" in decisions:
            self.state.set_mode(AgentMode.DEPOSITING)
            await self.supply_manager.start_depot_run()
            log.info("strategic.returning_depot", reason=decisions.get("reason", "supplies low"))

        if "explore" in decisions:
            explore = decisions["explore"]
            strategy_name = explore.get("strategy", "FRONTIER")
            try:
                strategy = ExploreStrategy[strategy_name]
            except KeyError:
                strategy = ExploreStrategy.FRONTIER
            reason = explore.get("reason", "strategic decision")

            self.explorer.start_exploration(strategy, reason=reason)
            self.state.set_mode(AgentMode.EXPLORING)
            log.info("strategic.exploration_started",
                     strategy=strategy.name, reason=reason)

        if "stop_explore" in decisions:
            stop = decisions["stop_explore"]
            if self.explorer.active:
                findings = self.explorer.stop_exploration()
                self.consciousness.remember(
                    "exploration",
                    f"Strategic stop: {stop.get('reason', '?')}. "
                    f"Targets: {findings['targets_reached']}, "
                    f"Waypoints: {findings['waypoints_generated']}",
                    importance=0.7,
                    tags=["exploration", "strategic_stop"],
                )
                if stop.get("generate_skill"):
                    skill_data = self.explorer.generate_skill_from_exploration()
                    if skill_data:
                        await self.skill_engine.save_skill_from_data(skill_data)
                        log.info("strategic.exploration_skill_saved",
                                 name=skill_data["name"])
                self.state.set_mode(AgentMode.HUNTING)

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
            # Queue corpse for looting
            # (position would come from creature tracking)

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
