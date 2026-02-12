"""
NEXUS — Strategic Loop

Deep thinking loop using Claude API.
Runs every 3-5 seconds (configurable).
Also contains the decision application logic.
"""

from __future__ import annotations

import time
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

from core.state.enums import AgentMode
from actions.explorer import ExploreStrategy

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Strategic brain cycle — deep thinking via Claude API."""
    import asyncio

    cycle_time = agent.config["ai"]["strategic_cycle_seconds"]

    while agent.running:
        try:
            if (agent.state.is_alive
                    and agent.state.mode != AgentMode.PAUSED
                    and not agent.recovery.recovery_active):
                snapshot = agent.state.get_snapshot()
                decisions = await agent.strategic_brain.think(snapshot)
                if decisions:
                    await apply_decisions(agent, decisions)
                agent.state.last_strategic_update = time.time()

        except Exception as e:
            log.error("strategic.error", error=str(e))

        await asyncio.sleep(cycle_time)


async def apply_decisions(agent: NexusAgent, decisions: dict) -> None:
    """
    Apply decisions from strategic brain to all subsystems.
    Each decision is wrapped individually — one bad decision
    doesn't prevent the rest from executing.
    """
    applied = 0
    failed = 0

    # --- change_mode ---
    if "change_mode" in decisions:
        try:
            mode_str = decisions["change_mode"]
            new_mode = AgentMode[mode_str]
            agent.state.set_mode(new_mode)
            log.info("strategic.mode_change", new_mode=new_mode.name)
            if new_mode == AgentMode.FLEEING:
                agent.navigator.start_escape()
            elif agent.navigator.is_escaping:
                agent.navigator.stop_escape()
            applied += 1
        except (KeyError, ValueError) as e:
            failed += 1
            log.warning("strategic.invalid_decision",
                        key="change_mode", value=decisions["change_mode"],
                        error=str(e))

    # --- adjust_healing ---
    if "adjust_healing" in decisions:
        try:
            agent.reactive_brain.update_healing_thresholds(decisions["adjust_healing"])
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="adjust_healing", error=str(e))

    # --- adjust_aggression ---
    if "adjust_aggression" in decisions:
        try:
            aggro = decisions["adjust_aggression"]
            agent.reactive_brain.update_aggression(aggro)
            log.info("strategic.aggression_adjusted", settings=aggro)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="adjust_aggression", error=str(e))

    # --- spell_rotation_override ---
    if "spell_rotation_override" in decisions:
        try:
            rotation = decisions["spell_rotation_override"]
            agent.reactive_brain.set_spell_rotation(rotation)
            log.info("strategic.rotation_override", rotation=rotation)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="spell_rotation_override", error=str(e))

    # --- reposition ---
    if "reposition" in decisions:
        try:
            repo = decisions["reposition"]
            direction = repo.get("direction", "")
            agent.reactive_brain.set_reposition_target(direction)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="reposition", error=str(e))

    # --- change_target ---
    if "change_target" in decisions:
        try:
            target_name = decisions["change_target"]
            for creature in agent.state.battle_list:
                if creature.name == target_name:
                    agent.state.current_target = creature
                    break
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="change_target", error=str(e))

    # --- change_skill ---
    if "change_skill" in decisions:
        try:
            new_skill_name = decisions["change_skill"]
            loaded = await agent.skill_engine.activate_skill(new_skill_name)
            if loaded:
                skill = agent.skill_engine.skills[new_skill_name]
                agent._activate_skill(skill)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="change_skill", error=str(e))

    # --- create_skill ---
    if "create_skill" in decisions:
        try:
            skill_request = decisions["create_skill"]
            log.info("strategic.creating_skill", request=skill_request)
            agent.state.set_mode(AgentMode.CREATING_SKILL)
            new_skill = await agent.skill_engine.create_skill(skill_request)
            if new_skill:
                agent._activate_skill(new_skill)
            agent.state.set_mode(AgentMode.HUNTING)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="create_skill", error=str(e))
            # Ensure mode is reset even on failure
            try:
                agent.state.set_mode(AgentMode.HUNTING)
            except Exception:
                pass

    # --- return_to_depot ---
    if "return_to_depot" in decisions:
        try:
            agent.state.set_mode(AgentMode.DEPOSITING)
            await agent.supply_manager.start_depot_run()
            log.info("strategic.returning_depot", reason=decisions.get("reason", "supplies low"))
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="return_to_depot", error=str(e))

    # --- explore ---
    if "explore" in decisions:
        try:
            explore = decisions["explore"]
            strategy_name = explore.get("strategy", "FRONTIER")
            try:
                strategy = ExploreStrategy[strategy_name]
            except KeyError:
                strategy = ExploreStrategy.FRONTIER
            reason = explore.get("reason", "strategic decision")
            agent.explorer.start_exploration(strategy, reason=reason)
            agent.state.set_mode(AgentMode.EXPLORING)
            log.info("strategic.exploration_started",
                     strategy=strategy.name, reason=reason)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="explore", error=str(e))

    # --- stop_explore ---
    if "stop_explore" in decisions:
        try:
            stop = decisions["stop_explore"]
            if agent.explorer.active:
                findings = agent.explorer.stop_exploration()
                agent.consciousness.remember(
                    "exploration",
                    f"Strategic stop: {stop.get('reason', '?')}. "
                    f"Targets: {findings['targets_reached']}, "
                    f"Waypoints: {findings['waypoints_generated']}",
                    importance=0.7,
                    tags=["exploration", "strategic_stop"],
                )
                if stop.get("generate_skill"):
                    skill_data = agent.explorer.generate_skill_from_exploration()
                    if skill_data:
                        await agent.skill_engine.save_skill_from_data(skill_data)
                        log.info("strategic.exploration_skill_saved",
                                 name=skill_data["name"])
                agent.state.set_mode(AgentMode.HUNTING)
            applied += 1
        except Exception as e:
            failed += 1
            log.warning("strategic.decision_error", key="stop_explore", error=str(e))

    if failed > 0:
        log.warning("strategic.decisions_summary",
                    applied=applied, failed=failed, total=len(decisions))
