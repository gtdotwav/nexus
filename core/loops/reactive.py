"""
NEXUS — Reactive Loop

Fast decision loop for survival actions.
Runs every 25ms (40 ticks/second).
Only handles: healing, anti-PK, combat, mana restore.
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
    """Reactive brain tick — instinct-level decisions."""
    import asyncio

    tick_rate = agent.config["reactive"]["tick_rate_ms"] / 1000

    while agent.running:
        start = time.perf_counter()

        try:
            if (agent.state.is_alive
                    and agent.state.mode != AgentMode.PAUSED
                    and not agent.recovery.recovery_active):
                await agent.reactive_brain.tick()

        except Exception as e:
            log.error("reactive.error", error=str(e))

        elapsed = time.perf_counter() - start
        sleep_time = max(0, tick_rate - elapsed)
        await asyncio.sleep(sleep_time)
