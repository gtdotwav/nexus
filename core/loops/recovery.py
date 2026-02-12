"""
NEXUS — Recovery Loop

Death recovery loop.
Continuously monitors for death and manages the recovery pipeline.
Runs every 500ms.
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

from core.state.enums import AgentMode

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Death detection and autonomous recovery."""
    import asyncio

    while agent.running:
        try:
            action = await agent.recovery.tick()

            if action == "death_detected":
                agent.state.set_mode(AgentMode.HEALING_CRITICAL)
                log.info("recovery.death_handling_started")

            elif action == "respawned":
                agent.state.set_mode(AgentMode.NAVIGATING)
                # Notify consciousness for learning
                agent.consciousness.remember(
                    "recovery",
                    f"Respawned after death #{agent.recovery.total_recoveries}. "
                    f"Consecutive: {agent.recovery.consecutive_deaths}",
                    importance=0.6,
                    tags=["death", "recovery"],
                )

            elif action == "returning_to_hunt":
                # Resume navigation to hunting area
                agent.navigator.current_index = 0
                agent.state.set_mode(AgentMode.NAVIGATING)

            elif action == "recovery_complete":
                agent.state.set_mode(AgentMode.HUNTING)
                log.info("recovery.complete_returning_to_hunt")

                # Check if we should change area (too many consecutive deaths)
                if agent.recovery.should_change_area:
                    agent.consciousness.remember(
                        "strategy",
                        f"Died {agent.recovery.consecutive_deaths} times consecutively. "
                        "Should consider area change or strategy revision.",
                        importance=0.9,
                        tags=["death_pattern", "area_change"],
                    )

        except Exception as e:
            log.error("recovery.error", error=str(e))

        await asyncio.sleep(0.5)
