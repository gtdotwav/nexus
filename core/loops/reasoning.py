"""
NEXUS — Reasoning Loop

Local reasoning loop — real-time inference with zero API latency.
Runs every 2-3 seconds. Analyzes spatial memory + game state
and produces actionable inferences for the strategic brain.
Also feeds observations back to spatial memory (damage, loot, deaths).
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

from core.state.enums import AgentMode
from actions.explorer import ExploreStrategy

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Local real-time reasoning — zero API latency inference."""
    import asyncio

    while agent.running:
        try:
            if (agent.state.is_alive
                    and agent.state.mode != AgentMode.PAUSED
                    and not agent.recovery.recovery_active):

                profile = await agent.reasoning_engine.analyze()

                # Auto-trigger exploration if in unknown territory
                if (profile.topology == "unknown"
                        and agent.state.mode == AgentMode.HUNTING
                        and not agent.explorer.active
                        and profile.recommended_action == "explore"):
                    log.info("reasoning.auto_explore_trigger",
                             reason="unknown_topology")
                    agent.explorer.start_exploration(
                        ExploreStrategy.SAFE, reason="unknown_territory_detected")
                    agent.state.set_mode(AgentMode.EXPLORING)

                # Auto-retreat if reasoning strongly recommends it
                if (profile.recommended_action == "retreat"
                        and agent.state.mode == AgentMode.EXPLORING
                        and agent.explorer.active):
                    log.info("reasoning.auto_retreat",
                             warnings=profile.warnings)
                    agent.explorer.strategy = ExploreStrategy.RETURN

        except Exception as e:
            log.error("reasoning.error", error=str(e))

        await asyncio.sleep(2.5)
