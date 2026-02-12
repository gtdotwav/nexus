"""
NEXUS — Abstract Game Adapter

The universal interface between NEXUS and any game.
Every game adapter must implement this interface.

The adapter is responsible for:
    1. PERCEPTION — Capturing and interpreting the game screen
    2. INPUT — Sending keyboard/mouse commands to the game
    3. STATE — Parsing game state from visual/memory data
    4. CONFIG — Providing game-specific default configuration

The NEXUS core (consciousness, strategic brain, foundry) is game-agnostic.
It operates on abstract concepts: HP, mana, creatures, position, inventory.
The adapter translates these to/from the specific game's representation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

import numpy as np


class GameCapability(Enum):
    """Capabilities a game adapter can declare."""
    SCREEN_CAPTURE = auto()      # Can capture game screen
    MEMORY_READ = auto()         # Can read game memory (if allowed)
    MINIMAP = auto()             # Has a minimap to parse
    BATTLE_LIST = auto()         # Has a visible creature list
    CHAT_LOG = auto()            # Has parseable chat/log
    INVENTORY = auto()           # Can read inventory state
    HEALTH_BAR = auto()          # Has visible health/mana bars
    SKILL_BAR = auto()           # Has visible skill/spell bar
    MARKET = auto()              # Has an in-game market/auction
    PARTY = auto()               # Supports party/group play
    PVP = auto()                 # Has player-vs-player
    EXPLORATION = auto()         # Has explorable map/world
    CRAFTING = auto()            # Has crafting system
    QUEST_LOG = auto()           # Has trackable quests
    HOTKEYS = auto()             # Supports custom hotkeys


@dataclass
class GameInfo:
    """Metadata about a supported game."""
    id: str                          # Unique identifier (e.g., "tibia")
    name: str                        # Display name (e.g., "Tibia")
    version: str = "1.0"             # Adapter version
    genre: str = "mmorpg"            # Game genre
    perspective: str = "2d_topdown"  # "2d_topdown", "2d_side", "3d_third", "3d_first"
    capabilities: list[GameCapability] = field(default_factory=list)
    description: str = ""
    author: str = ""
    min_resolution: tuple[int, int] = (800, 600)
    recommended_resolution: tuple[int, int] = (1920, 1080)


@dataclass
class PerceptionResult:
    """Standardized output from game perception."""
    # Character state
    hp_percent: float = 100.0
    mana_percent: float = 100.0
    position: Optional[tuple[int, int, int]] = None  # (x, y, z)

    # Combat
    battle_list: list[dict] = field(default_factory=list)
    nearby_players: list[dict] = field(default_factory=list)
    current_target: Optional[dict] = None
    in_combat: bool = False

    # Minimap
    minimap_data: Optional[np.ndarray] = None

    # Inventory & supplies
    supplies: dict[str, int] = field(default_factory=dict)

    # Chat / log messages
    chat_messages: list[dict] = field(default_factory=list)

    # Raw frame (for debugging / spatial memory)
    frame: Optional[np.ndarray] = None

    # Game-specific extras
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class InputAction:
    """A standardized input action."""
    action_type: str       # "key_press", "key_hold", "mouse_click", "mouse_move", "hotkey"
    key: str = ""          # Key name or hotkey combo
    x: int = 0             # Mouse X (screen coords)
    y: int = 0             # Mouse Y (screen coords)
    duration: float = 0.0  # Hold duration in seconds
    modifiers: list[str] = field(default_factory=list)  # ["shift", "ctrl", etc.]
    delay_after: float = 0.05  # Delay after action


class GameAdapter(ABC):
    """
    Abstract base class for game adapters.

    Implement this to add support for a new game.
    The adapter bridges NEXUS's abstract intelligence with a specific game.
    """

    @abstractmethod
    def get_info(self) -> GameInfo:
        """Return metadata about this game adapter."""
        ...

    @abstractmethod
    async def initialize(self, config: dict) -> bool:
        """
        Initialize the adapter.
        Set up screen capture, calibrate regions, detect game window.
        Returns True if game is found and ready.
        """
        ...

    @abstractmethod
    async def capture_and_parse(self) -> PerceptionResult:
        """
        Capture the game screen and parse it into a PerceptionResult.
        This is called every perception tick (30+ fps).
        Must be fast — target <10ms for capture + basic parsing.
        """
        ...

    @abstractmethod
    async def send_input(self, action: InputAction) -> bool:
        """
        Send an input action to the game.
        Returns True if the action was executed.
        """
        ...

    @abstractmethod
    async def detect_game_window(self) -> bool:
        """
        Detect if the game is running and find its window.
        Returns True if found.
        """
        ...

    @abstractmethod
    def get_default_config(self) -> dict:
        """
        Return the default configuration for this game.
        Used by the setup wizard and for config generation.
        """
        ...

    @abstractmethod
    def get_screen_regions(self) -> dict[str, tuple[int, int, int, int]]:
        """
        Return named screen regions for this game.
        e.g., {"health_bar": (x, y, w, h), "minimap": (x, y, w, h), ...}
        Used for calibration and perception.
        """
        ...

    # ─── Optional overrides ──────────────────────────────

    async def on_start(self):
        """Called when the agent starts a session."""
        pass

    async def on_stop(self):
        """Called when the agent ends a session."""
        pass

    async def calibrate(self) -> dict:
        """
        Run interactive calibration.
        Returns calibration data to store in config.
        """
        return {}

    def translate_action(self, abstract_action: str, params: dict) -> list[InputAction]:
        """
        Translate an abstract action (e.g., "heal", "attack", "move_north")
        into game-specific input actions.
        Override for game-specific action mappings.
        """
        return []

    def get_skill_template(self) -> str:
        """Return a YAML template for creating new skills for this game."""
        return ""
