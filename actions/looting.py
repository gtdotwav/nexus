"""
NEXUS Agent — Loot Engine

Handles all loot-related operations:
- Corpse detection on game screen
- Right-click to open corpse
- Identify valuable items vs trash
- Pick up valuable items
- Stack gold/platinum coins
- Track loot value for session metrics

Uses skill configuration to decide what to keep vs ignore.
"""

from __future__ import annotations

import asyncio
import time
import random
import structlog
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState

log = structlog.get_logger()


@dataclass
class LootItem:
    """Represents a looted item."""
    name: str
    value: int = 0
    stackable: bool = False
    timestamp: float = field(default_factory=time.time)


class LootEngine:
    """
    Manages corpse looting and item management.

    Looting pipeline:
        1. Detect corpse (from battle list creature death or screen scan)
        2. Right-click corpse tile
        3. Read loot window contents (OCR)
        4. Filter: keep valuables, ignore trash
        5. Drag valuable items to inventory
        6. Close loot window
        7. Track loot value

    Integrates with skill config for item classification.
    """

    def __init__(self, state: "GameState", input_handler, config: dict):
        self.state = state
        self.input = input_handler
        self.config = config

        # Loot configuration (loaded from active skill)
        self.valuable_items: set[str] = set()
        self.ignore_items: set[str] = set()
        self.auto_loot: bool = True
        self.loot_delay_ms: int = 500

        # Queue of corpses to loot (game positions)
        self._corpse_queue: list[dict] = []
        self._looting: bool = False
        self._last_loot_time: float = 0
        self._loot_cooldown: float = 1.0   # Min seconds between loot attempts

        # Session tracking
        self.items_looted: int = 0
        self.total_value: int = 0
        self.loot_log: list[LootItem] = []

    def load_loot_config(self, loot_config: dict):
        """Load loot configuration from active skill."""
        self.auto_loot = loot_config.get("auto_loot", True)
        self.loot_delay_ms = loot_config.get("loot_delay_ms", 500)
        self.valuable_items = set(
            item.lower() for item in loot_config.get("valuable_items", [])
        )
        self.ignore_items = set(
            item.lower() for item in loot_config.get("ignore_items", [])
        )
        log.info("loot.config_loaded",
                 valuable=len(self.valuable_items),
                 ignore=len(self.ignore_items))

    def queue_corpse(self, x: int, y: int, z: int, creature_name: str = ""):
        """Add a corpse position to the loot queue."""
        self._corpse_queue.append({
            "x": x, "y": y, "z": z,
            "creature": creature_name,
            "time": time.time(),
        })
        log.debug("loot.corpse_queued", creature=creature_name,
                   queue_size=len(self._corpse_queue))

    async def tick(self) -> Optional[str]:
        """
        Process one loot tick. Returns action taken or None.

        Called by reactive brain at lower priority than healing/combat.
        """
        if not self.auto_loot or self._looting:
            return None

        now = time.time()
        if now - self._last_loot_time < self._loot_cooldown:
            return None

        # Clean old corpses (older than 30s — they've probably decayed)
        self._corpse_queue = [
            c for c in self._corpse_queue
            if now - c["time"] < 30
        ]

        if not self._corpse_queue:
            return None

        # Loot the nearest corpse
        corpse = self._corpse_queue.pop(0)
        return await self._loot_corpse(corpse)

    async def _loot_corpse(self, corpse: dict) -> str:
        """Execute the full looting sequence for a single corpse."""
        self._looting = True
        creature = corpse.get("creature", "unknown")

        try:
            # Step 1: Right-click the corpse tile on game screen
            screen_pos = self._game_to_screen(corpse["x"], corpse["y"])
            if screen_pos:
                # Right-click to open corpse
                await self.input.click(screen_pos[0], screen_pos[1], button="right")
                await asyncio.sleep(self.loot_delay_ms / 1000)

                # Step 2: Check if loot window appeared
                # In Tibia, right-clicking a corpse shows loot in a container
                # For now, we use the "auto-loot" approach (Tibia has built-in auto-loot)

                # Step 3: Shift+click for quick loot (Tibia shortcut)
                await self.input.click(
                    screen_pos[0], screen_pos[1],
                    button="left",
                    modifiers=["shift"]
                )

                self.items_looted += 1
                self._last_loot_time = time.time()

                log.debug("loot.collected", creature=creature,
                           total=self.items_looted)

                return "looted"
            else:
                return "corpse_not_visible"

        except Exception as e:
            log.error("loot.error", error=str(e))
            return "loot_error"

        finally:
            self._looting = False

    def _game_to_screen(self, game_x: int, game_y: int) -> Optional[tuple[int, int]]:
        """
        Convert game world coordinates to screen pixel position.

        The game viewport shows a grid of tiles centered on the player.
        Each tile is ~32x32 pixels (varies with resolution).
        """
        pos = self.state.position
        if pos is None:
            return None

        # Get game viewport config
        viewport = self.config.get("viewport", {})
        center_x = viewport.get("center_x", 960)  # Center of game screen
        center_y = viewport.get("center_y", 400)
        tile_size = viewport.get("tile_size", 32)

        # Delta from player position
        dx = game_x - pos.x
        dy = game_y - pos.y

        # Only loot visible tiles (within ~7 tile radius)
        if abs(dx) > 7 or abs(dy) > 7:
            return None

        # Convert to screen pixels
        screen_x = center_x + (dx * tile_size)
        screen_y = center_y + (dy * tile_size)

        # Add slight randomization for humanized clicking
        screen_x += random.randint(-4, 4)
        screen_y += random.randint(-4, 4)

        return (int(screen_x), int(screen_y))

    def is_valuable(self, item_name: str) -> bool:
        """Check if an item should be kept."""
        name = item_name.lower()
        if name in self.ignore_items:
            return False
        if self.valuable_items:
            return name in self.valuable_items
        # Default: keep everything that's not explicitly ignored
        return True

    def record_loot_value(self, value: int, item_name: str = ""):
        """Record a loot value from chat message parsing."""
        self.total_value += value
        self.loot_log.append(LootItem(name=item_name, value=value))

    @property
    def stats(self) -> dict:
        return {
            "items_looted": self.items_looted,
            "total_value": self.total_value,
            "queue_size": len(self._corpse_queue),
            "is_looting": self._looting,
        }
