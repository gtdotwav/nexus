"""
NEXUS — Consciousness Loop

ALWAYS-ON consciousness — runs at multiple frequencies simultaneously.
    - Instinct every 1s → emotional micro-ticks
    - Awareness every 10s → pattern recognition
    - Reflection every 2min → strategy assessment
    - Deep analysis every 10min → evolution triggers
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Multi-frequency consciousness tick."""
    import asyncio

    while agent.running:
        try:
            snapshot = agent.state.get_snapshot()
            char = snapshot.get("character", {})
            game_state = {
                "hp_percent": char.get("hp_percent", 100),
                "nearby_players": snapshot.get("combat", {}).get("nearby_players", []),
                "session": snapshot.get("session", {}),
                "mode": agent.state.mode.name,
                "recovery_active": agent.recovery.recovery_active,
            }

            await agent.consciousness.tick_instinct(game_state)
            await agent.consciousness.tick_awareness(game_state)
            await agent.consciousness.tick_reflection(game_state)

            deep_results = await agent.consciousness.tick_deep_analysis(game_state)
            if deep_results:
                await agent.foundry.process_consciousness_findings(deep_results, snapshot)

        except Exception as e:
            log.error("consciousness.error", error=str(e))

        await asyncio.sleep(1)
