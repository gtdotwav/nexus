"""
NEXUS — Metrics Loop

Updates session metrics every 60 seconds.
Logs performance data for monitoring and dashboard.
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()


async def run(agent: NexusAgent) -> None:
    """Session metrics tracking and logging."""
    import asyncio

    cycle_time = agent.config.get("metrics", {}).get("cycle_seconds", 60)

    while agent.running:
        try:
            elapsed_hours = agent.state.session_duration_minutes / 60
            if elapsed_hours > 0:
                agent.state.session.xp_per_hour = agent.state.session.xp_gained / elapsed_hours
                agent.state.session.profit_per_hour = agent.state.session.loot_value / elapsed_hours

            # Build metrics dict safely — avoid crashing on None attributes
            reasoning_action = "unknown"
            if agent.reasoning_engine and agent.reasoning_engine.current_profile:
                reasoning_action = agent.reasoning_engine.current_profile.recommended_action

            log.info(
                "metrics.update",
                xp_hr=round(agent.state.session.xp_per_hour),
                profit_hr=round(agent.state.session.profit_per_hour),
                deaths=agent.state.session.deaths,
                kills=agent.state.session.kills,
                mode=agent.state.mode.name,
                threat=agent.state.threat_level.name,
                nav=f"WP{agent.navigator.current_index}/{len(agent.navigator.active_route or [])}",
                loot=agent.loot_engine.items_looted,
                depot_runs=agent.supply_manager.depot_runs,
                map_cells=agent.spatial_memory.total_cells_explored,
                map_floors=len(agent.spatial_memory.floors),
                reasoning=reasoning_action,
                exploring=agent.explorer.active,
                perception_ms=agent.game_reader.avg_frame_ms,
                event_bus=agent.event_bus.stats,
                strategic_calls=agent.strategic_brain.calls,
                strategic_skipped=agent.strategic_brain.skipped_calls,
            )
        except Exception as e:
            log.error("metrics.error", error=str(e), type=type(e).__name__)

        await asyncio.sleep(cycle_time)
