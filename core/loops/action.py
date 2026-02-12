"""
NEXUS — Action Loop

Action execution loop for non-combat actions.
Runs every 100ms (10 ticks/second).
Handles: navigation, looting, supply checks, behaviors, exploration.
Lower priority than reactive — only runs when not in combat danger.
"""

from __future__ import annotations

import time
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

from core.state.enums import AgentMode

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Action execution — navigation, loot, supply, exploration."""
    import asyncio

    while agent.running:
        start = time.perf_counter()

        try:
            if (agent.state.is_alive
                    and agent.state.mode != AgentMode.PAUSED
                    and not agent.recovery.recovery_active):

                # Supply manager — always monitoring
                supply_action = await agent.supply_manager.tick()
                if supply_action == "needs_depot":
                    agent.state.set_mode(AgentMode.DEPOSITING)
                    await agent.supply_manager.start_depot_run()

                # Navigation — runs when not in immediate combat
                if agent.state.mode in (AgentMode.HUNTING, AgentMode.NAVIGATING,
                                        AgentMode.DEPOSITING, AgentMode.FLEEING):
                    nav_action = await agent.navigator.tick()

                    # Handle navigator reaching depot
                    if nav_action == "at_depot" and agent.supply_manager.depot_run_active:
                        agent.supply_manager.notify_arrived_at_depot()

                # Explorer — when in exploration mode
                if agent.state.mode == AgentMode.EXPLORING and agent.explorer.active:
                    explore_action = await agent.explorer.tick()

                    if explore_action == "no_targets":
                        # Exploration complete — generate skill if possible
                        skill_data = agent.explorer.generate_skill_from_exploration()
                        findings = agent.explorer.stop_exploration()
                        agent.consciousness.remember(
                            "exploration",
                            f"Exploration complete: {findings['targets_reached']} targets, "
                            f"{findings['waypoints_generated']} waypoints discovered",
                            importance=0.8,
                            tags=["exploration", "map_discovery"],
                        )
                        if skill_data:
                            log.info("nexus.exploration_skill_generated",
                                     name=skill_data["name"])
                            await agent.skill_engine.save_skill_from_data(skill_data)
                        agent.state.set_mode(AgentMode.HUNTING)

                # Looting — only when safe
                if agent.state.mode in (AgentMode.HUNTING, AgentMode.EXPLORING):
                    await agent.loot_engine.tick()

                # Behaviors — food, buffs, pull monsters, positioning
                if agent.state.mode in (AgentMode.HUNTING, AgentMode.NAVIGATING,
                                        AgentMode.EXPLORING):
                    await agent.behavior_engine.tick()

        except Exception as e:
            log.error("actions.error", error=str(e))

        elapsed = time.perf_counter() - start
        sleep_time = max(0, 0.1 - elapsed)
        await asyncio.sleep(sleep_time)
