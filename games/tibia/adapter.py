"""
NEXUS — Tibia Game Adapter

Bridges NEXUS's abstract intelligence with Tibia's specific UI.
Handles screen capture, OCR, minimap parsing, battle list reading,
health bar detection, and keyboard/mouse input for Tibia.

Tibia specifics:
    - 2D top-down perspective
    - Minimap in top-right corner
    - Battle list on right side panel
    - Health/Mana bars below the game window
    - Chat log at the bottom
    - Uses hotkeys for spells and items
    - Auto-loot via shift+click on corpses
"""

from __future__ import annotations

import asyncio
import sys
import structlog
from typing import Optional

from games.base import (
    GameAdapter,
    GameCapability,
    GameInfo,
    InputAction,
    PerceptionResult,
)

log = structlog.get_logger()


class TibiaAdapter(GameAdapter):
    """
    Tibia MMORPG adapter.

    Wraps the existing NEXUS perception and input systems
    into the standardized GameAdapter interface.
    """

    def __init__(self):
        self.screen_capture = None
        self.game_reader = None
        self.input_controller = None
        self._config: dict = {}
        self._initialized = False
        self._window_found = False

    def get_info(self) -> GameInfo:
        return GameInfo(
            id="tibia",
            name="Tibia",
            version="0.1.0",
            genre="mmorpg",
            perspective="2d_topdown",
            capabilities=[
                GameCapability.SCREEN_CAPTURE,
                GameCapability.MINIMAP,
                GameCapability.BATTLE_LIST,
                GameCapability.CHAT_LOG,
                GameCapability.HEALTH_BAR,
                GameCapability.SKILL_BAR,
                GameCapability.INVENTORY,
                GameCapability.HOTKEYS,
                GameCapability.PVP,
                GameCapability.EXPLORATION,
                GameCapability.MARKET,
            ],
            description=(
                "Tibia is a 2D top-down MMORPG. NEXUS uses vision-based perception "
                "to read the game screen, parse the minimap, battle list, and health bars, "
                "then sends keyboard/mouse inputs for combat, navigation, and looting."
            ),
            author="NEXUS Team",
            min_resolution=(800, 600),
            recommended_resolution=(1920, 1080),
        )

    async def initialize(self, config: dict) -> bool:
        """Initialize Tibia-specific capture and input systems."""
        self._config = config

        try:
            from perception.screen_capture import ScreenCapture
            from perception.game_reader_v2 import GameReaderV2
            from core.state import GameState

            state = GameState()
            self.screen_capture = ScreenCapture(config.get("perception", {}))
            self.game_reader = GameReaderV2(state, config.get("perception", {}))

            await self.screen_capture.initialize()
            self._initialized = True

            log.info("tibia_adapter.initialized")
            return True

        except Exception as e:
            log.error("tibia_adapter.init_error", error=str(e))
            return False

    async def capture_and_parse(self) -> PerceptionResult:
        """Capture Tibia screen and parse into standardized result."""
        if not self._initialized or not self.screen_capture:
            return PerceptionResult()

        try:
            frame = await self.screen_capture.capture()
            if frame is None:
                return PerceptionResult()

            # The game_reader updates the state object directly
            await self.game_reader.process_frame(frame)

            state = self.game_reader.state
            char = state.character

            return PerceptionResult(
                hp_percent=char.hp_percent if hasattr(char, "hp_percent") else 100,
                mana_percent=char.mana_percent if hasattr(char, "mana_percent") else 100,
                position=(state.position.x, state.position.y, state.position.z)
                if state.position else None,
                battle_list=[
                    {
                        "name": c.name,
                        "hp": c.hp_percent,
                        "distance": c.distance,
                        "is_player": c.is_player,
                    }
                    for c in state.battle_list
                ],
                nearby_players=[
                    {
                        "name": c.name,
                        "skull": c.skull,
                    }
                    for c in state.battle_list if c.is_player
                ],
                in_combat=state.mode.name in ("HUNTING", "FLEEING"),
                frame=frame,
            )

        except Exception as e:
            log.error("tibia_adapter.capture_error", error=str(e))
            return PerceptionResult()

    async def send_input(self, action: InputAction) -> bool:
        """Send input to Tibia window."""
        try:
            from pynput.keyboard import Controller as KbController, Key
            from pynput.mouse import Controller as MouseController, Button

            kb = KbController()
            mouse = MouseController()

            if action.action_type == "key_press":
                # Map special keys
                key_map = {
                    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
                    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
                    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
                    "enter": Key.enter, "esc": Key.esc, "space": Key.space,
                    "tab": Key.tab, "up": Key.up, "down": Key.down,
                    "left": Key.left, "right": Key.right,
                }
                key = key_map.get(action.key.lower(), action.key)

                # Handle modifiers
                held = []
                for mod in action.modifiers:
                    mod_key = {"shift": Key.shift, "ctrl": Key.ctrl,
                               "alt": Key.alt}.get(mod.lower())
                    if mod_key:
                        kb.press(mod_key)
                        held.append(mod_key)

                kb.press(key)
                if action.duration > 0:
                    await asyncio.sleep(action.duration)
                kb.release(key)

                for mod_key in reversed(held):
                    kb.release(mod_key)

            elif action.action_type == "mouse_click":
                mouse.position = (action.x, action.y)
                await asyncio.sleep(0.02)

                button = Button.right if "right" in action.key else Button.left
                mouse.click(button)

            elif action.action_type == "mouse_move":
                mouse.position = (action.x, action.y)

            if action.delay_after > 0:
                await asyncio.sleep(action.delay_after)

            return True

        except Exception as e:
            log.error("tibia_adapter.input_error", error=str(e), action=action.action_type)
            return False

    async def detect_game_window(self) -> bool:
        """Detect if Tibia is running."""
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32

                def enum_cb(hwnd, results):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            if "tibia" in buf.value.lower():
                                results.append(hwnd)
                    return True

                results = []
                WNDENUMPROC = ctypes.WINFUNCTYPE(
                    ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
                )
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
                self._window_found = len(results) > 0
                return self._window_found

            except Exception:
                pass

        elif sys.platform == "darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e",
                     'tell application "System Events" to get name of every process '
                     'whose name contains "Tibia"'],
                    capture_output=True, text=True, timeout=5,
                )
                self._window_found = "Tibia" in result.stdout
                return self._window_found
            except Exception:
                pass

        # Fallback: check processes
        try:
            import subprocess
            result = subprocess.run(
                ["pgrep", "-i", "tibia"],
                capture_output=True, text=True, timeout=5,
            )
            self._window_found = result.returncode == 0
            return self._window_found
        except Exception:
            pass

        return False

    def get_default_config(self) -> dict:
        """Return default Tibia configuration."""
        return {
            "agent": {
                "game": "tibia",
                "character_name": "YourCharacter",
                "server": "YourServer",
            },
            "perception": {
                "capture": {
                    "method": "dxcam" if sys.platform == "win32" else "screenshot",
                    "fps": 30,
                    "game_window_title": "Tibia",
                },
                "screen_regions": self.get_screen_regions(),
            },
            "reactive": {
                "tick_rate_ms": 25,
                "healing": {
                    "critical_hp": 30,
                    "medium_hp": 60,
                    "mana_threshold": 50,
                },
                "hotkeys": {
                    "heal_critical": "F1",
                    "heal_medium": "F2",
                    "mana_potion": "F3",
                    "haste": "F4",
                    "attack_spell": "F5",
                    "area_spell": "F6",
                    "exeta_res": "F7",
                    "ultimate_heal": "F8",
                },
            },
            "ai": {
                "model_strategic": "claude-sonnet-4-20250514",
                "model_skill_creation": "claude-sonnet-4-20250514",
                "strategic_cycle_seconds": 3,
                "max_tokens": 1024,
                "temperature": 0.2,
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "input": {
                "human_delay_min_ms": 30,
                "human_delay_max_ms": 80,
                "click_variance_px": 3,
            },
            "skills": {
                "directory": "skills/tibia",
                "auto_create": True,
                "auto_improve": True,
                "improvement_threshold": 80,
            },
            "navigation": {
                "stuck_threshold_ticks": 5,
                "minimap_click_offset": {"x": 0, "y": 0},
            },
            "exploration": {
                "max_deaths_before_retreat": 3,
                "frontier_refresh_interval": 30,
                "auto_skill_generation": True,
            },
            "dashboard": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8420,
            },
        }

    def get_screen_regions(self) -> dict[str, tuple[int, int, int, int]]:
        """
        Default screen regions for Tibia at 1920x1080.
        These are calibrated during first run.
        Format: (x, y, width, height)
        """
        return {
            "game_area": (0, 0, 1440, 900),
            "minimap": (1600, 0, 320, 240),
            "health_bar": (0, 900, 200, 20),
            "mana_bar": (0, 920, 200, 20),
            "battle_list": (1440, 240, 480, 400),
            "chat": (0, 940, 1440, 140),
            "inventory": (1440, 640, 480, 200),
            "skill_bar": (400, 900, 800, 40),
        }

    def translate_action(self, abstract_action: str, params: dict) -> list[InputAction]:
        """Translate abstract actions into Tibia-specific inputs."""
        hotkeys = self._config.get("reactive", {}).get("hotkeys", {})

        translations = {
            "heal_critical": [InputAction(
                action_type="key_press",
                key=hotkeys.get("heal_critical", "F1"),
            )],
            "heal_medium": [InputAction(
                action_type="key_press",
                key=hotkeys.get("heal_medium", "F2"),
            )],
            "use_mana_potion": [InputAction(
                action_type="key_press",
                key=hotkeys.get("mana_potion", "F3"),
            )],
            "attack": [InputAction(
                action_type="key_press",
                key=hotkeys.get("attack_spell", "F5"),
            )],
            "move_north": [InputAction(action_type="key_press", key="up")],
            "move_south": [InputAction(action_type="key_press", key="down")],
            "move_east": [InputAction(action_type="key_press", key="right")],
            "move_west": [InputAction(action_type="key_press", key="left")],
            "loot": [InputAction(
                action_type="mouse_click",
                key="right",
                x=params.get("x", 0),
                y=params.get("y", 0),
                modifiers=["shift"],
            )],
        }

        return translations.get(abstract_action, [])

    def get_skill_template(self) -> str:
        """Return a YAML template for creating Tibia hunting skills."""
        return """# NEXUS Tibia Skill Template
name: "skill_name_here"
game: tibia
version: "1.0"
category: hunting

metadata:
  level_range: [100, 200]
  vocation: "Elite Knight"
  location: "Area Name"
  expected_xp_hr: 500000

healing:
  critical:
    hp_threshold: 30
    spells: ["exura gran ico"]
    potions: ["ultimate health potion"]
  medium:
    hp_threshold: 60
    spells: ["exura ico"]
    potions: ["health potion"]
  mana:
    threshold: 50
    potions: ["great mana potion"]

targeting:
  - name: "Dragon"
    priority: 1
    approach: true
    attack_spells: ["exori gran", "exori"]
  - name: "Dragon Lord"
    priority: 2
    approach: false
    attack_spells: ["exori gran"]

waypoints:
  - {x: 100, y: 100, z: 7, action: "walk"}
  - {x: 110, y: 100, z: 7, action: "hunt_area", radius: 5}
  - {x: 100, y: 110, z: 7, action: "loot_check"}

supplies:
  health_potions: {min: 100, buy: 500}
  mana_potions: {min: 200, buy: 800}
  depot_location: {x: 90, y: 90, z: 7}

anti_pk:
  flee_hp: 40
  logout_hp: 20
  escape_waypoints:
    - {x: 80, y: 80, z: 7}
"""
