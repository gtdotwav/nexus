"""
NEXUS Game Adapter System.

Each game is a pluggable adapter that implements the GameAdapter interface.
This allows NEXUS to expand to any game — the core AI, consciousness,
and learning systems remain the same. Only the perception and input layers change.

Supported games:
    - tibia: Tibia MMORPG (2D, vision-based)

Adding a new game:
    1. Create a new module under games/ (e.g., games/poe/)
    2. Implement GameAdapter interface
    3. Register in GAME_REGISTRY
    4. Create game-specific config in config/
    5. Create game-specific skills in skills/
"""

from games.registry import GAME_REGISTRY, get_adapter, list_games

__all__ = ["GAME_REGISTRY", "get_adapter", "list_games"]
