"""
NEXUS — Evolution Loop

Foundry continuous evolution.
Waits 180s for data accumulation, then runs every 60s.
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Foundry self-evolution cycle."""
    import asyncio

    await asyncio.sleep(180)  # Let data accumulate first

    while agent.running:
        try:
            if agent.state.is_alive:
                snapshot = agent.state.get_snapshot()
                await agent.foundry.evolution_cycle(snapshot)
        except Exception as e:
            log.error("evolution.error", error=str(e))

        await asyncio.sleep(60)
