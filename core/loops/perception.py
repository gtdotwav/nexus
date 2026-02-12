"""
NEXUS — Perception Loop

Captures screen and updates game state.
Runs at configured FPS (default 30fps = ~33ms per frame).
Also feeds spatial memory with real-time observations.
"""

from __future__ import annotations

import time
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Main perception loop — the agent's eyes."""
    import asyncio

    target_interval = 1.0 / agent.config["perception"]["capture"]["fps"]

    while agent.running:
        start = time.perf_counter()

        try:
            frame = await agent.screen_capture.capture()
            if frame is not None:
                await agent.game_reader.process_frame(frame)
                agent.state.last_perception_update = time.time()

                # Feed spatial memory with current observations
                pos = agent.state.position
                if pos:
                    agent.spatial_memory.observe_position(pos.x, pos.y, pos.z)

                    # Record creature positions from battle list
                    for creature in agent.state.battle_list:
                        agent.spatial_memory.observe_creature(
                            creature.name,
                            pos.x, pos.y, pos.z,
                            is_player=creature.is_player,
                        )

        except Exception as e:
            log.error("perception.error", error=str(e))

        elapsed = time.perf_counter() - start
        sleep_time = max(0, target_interval - elapsed)
        await asyncio.sleep(sleep_time)
