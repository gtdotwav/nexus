"""
NEXUS — Game Registry

Central registry for all supported game adapters.
New games register here to become available.
"""

from __future__ import annotations

import structlog
from typing import Optional, Type

from games.base import GameAdapter, GameInfo

log = structlog.get_logger()

# ═══════════════════════════════════════════════════════
#  Registry — Map of game_id → adapter class
# ═══════════════════════════════════════════════════════

GAME_REGISTRY: dict[str, Type[GameAdapter]] = {}


def register_game(game_id: str, adapter_class: Type[GameAdapter]):
    """Register a game adapter in the global registry."""
    GAME_REGISTRY[game_id] = adapter_class
    log.info("registry.game_registered", game=game_id, adapter=adapter_class.__name__)


def get_adapter(game_id: str) -> Optional[GameAdapter]:
    """Create and return a game adapter instance by ID."""
    cls = GAME_REGISTRY.get(game_id)
    if cls is None:
        log.error("registry.game_not_found", game=game_id,
                  available=list(GAME_REGISTRY.keys()))
        return None
    return cls()


def list_games() -> list[GameInfo]:
    """List all registered games with their metadata."""
    result = []
    for game_id, cls in GAME_REGISTRY.items():
        try:
            adapter = cls()
            result.append(adapter.get_info())
        except Exception as e:
            log.error("registry.info_error", game=game_id, error=str(e))
    return result


# ═══════════════════════════════════════════════════════
#  Auto-discover built-in adapters
# ═══════════════════════════════════════════════════════

def _auto_register():
    """Auto-register all built-in game adapters."""
    try:
        from games.tibia.adapter import TibiaAdapter
        register_game("tibia", TibiaAdapter)
    except ImportError as e:
        log.debug("registry.tibia_not_available", error=str(e))


_auto_register()
