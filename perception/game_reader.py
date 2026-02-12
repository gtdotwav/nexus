"""
DEPRECATED — Use perception/game_reader_v2.py instead.
This file is kept for backward compatibility and CI import checks only.

NEXUS Agent - Game State Reader (Legacy)

Extracts structured game data from screen captures.
Converts raw pixels into HP, Mana, creatures, position, etc.
"""

from __future__ import annotations

import asyncio
import time
import numpy as np
import cv2
import structlog
from typing import Optional

from core.state import GameState, CreatureState

log = structlog.get_logger()


class GameReader:
    """
    Reads game state from screen captures.

    Tibia-specific implementation:
        - HP/Mana from colored bar regions (pixel color → percentage)
        - Battle list from text region (OCR or template matching)
        - Position from minimap patterns
        - Chat from OCR on chat window region
    """

    def __init__(self, state: GameState, config: dict):
        self.state = state
        self.config = config
        self.regions = config["regions"]
        self._calibrated = False
        self._ocr_engine = None

        # Color ranges for bar detection (BGR format)
        # Tibia HP bar is red (full) to dark red (empty)
        self.HP_COLOR_FULL = np.array([0, 0, 192])     # Red
        self.HP_COLOR_EMPTY = np.array([48, 48, 48])    # Dark gray
        self.MANA_COLOR_FULL = np.array([192, 0, 0])    # Blue
        self.MANA_COLOR_EMPTY = np.array([48, 48, 48])  # Dark gray

    async def calibrate(self):
        """
        Calibrate the reader by detecting game window layout.
        This should run once at startup and when the window is resized.
        """
        log.info("game_reader.calibrating")

        # Initialize OCR engine
        try:
            import easyocr
            self._ocr_engine = easyocr.Reader(
                self.config["ocr"]["languages"],
                gpu=self.config["ocr"]["gpu"],
            )
            log.info("game_reader.ocr_initialized", engine="easyocr")
        except ImportError:
            log.warning("game_reader.ocr_unavailable", fallback="template_matching")

        self._calibrated = True
        log.info("game_reader.calibrated")

    async def process_frame(self, frame: np.ndarray):
        """
        Process a single frame and update game state.

        This is the main perception pipeline that runs every frame.
        Extracts all relevant game data from the screen capture.
        """
        if not self._calibrated or frame is None:
            return

        # Run extractors concurrently where possible
        # HP/Mana are the highest priority (needed for reactive brain)
        await asyncio.gather(
            self._read_hp_bar(frame),
            self._read_mana_bar(frame),
            self._read_battle_list(frame),
        )

        # Lower priority reads (can be less frequent)
        # These run on alternating frames to save CPU
        frame_num = int(time.time() * 10) % 10
        if frame_num % 3 == 0:
            await self._read_minimap(frame)
        if frame_num % 5 == 0:
            await self._read_chat(frame)

    async def _read_hp_bar(self, frame: np.ndarray):
        """
        Read HP percentage from the HP bar pixels.

        Method: Count red pixels in the HP bar region.
        The bar is a horizontal line where filled = red, empty = dark.
        HP% = (red_pixels / total_pixels) * 100
        """
        region = self.regions["hp_bar"]
        bar = frame[region["y"]:region["y"]+region["h"],
                     region["x"]:region["x"]+region["w"]]

        if bar.size == 0:
            return

        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)

        # Red in HSV (red wraps around in hue, need two ranges)
        mask1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([160, 100, 100]), np.array([180, 255, 255]))
        red_mask = mask1 | mask2

        # Calculate percentage
        total_pixels = bar.shape[1]  # Width of bar
        red_pixels = np.count_nonzero(red_mask[bar.shape[0]//2, :])  # Middle row

        hp_percent = (red_pixels / total_pixels) * 100 if total_pixels > 0 else 0

        # Update state (convert percent to actual values if we know max HP)
        # For now, store as percentage and assume max 1000 (will be calibrated)
        estimated_max = self.state.hp_max if self.state.hp_max > 0 else 1000
        self.state.update_hp(
            current=estimated_max * (hp_percent / 100),
            maximum=estimated_max
        )

    async def _read_mana_bar(self, frame: np.ndarray):
        """
        Read Mana percentage from the mana bar pixels.
        Same method as HP but looking for blue instead of red.
        """
        region = self.regions["mana_bar"]
        bar = frame[region["y"]:region["y"]+region["h"],
                     region["x"]:region["x"]+region["w"]]

        if bar.size == 0:
            return

        # Convert to HSV
        hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)

        # Blue in HSV
        blue_mask = cv2.inRange(hsv, np.array([100, 100, 100]), np.array([130, 255, 255]))

        total_pixels = bar.shape[1]
        blue_pixels = np.count_nonzero(blue_mask[bar.shape[0]//2, :])

        mana_percent = (blue_pixels / total_pixels) * 100 if total_pixels > 0 else 0

        estimated_max = self.state.mana_max if self.state.mana_max > 0 else 1000
        self.state.update_mana(
            current=estimated_max * (mana_percent / 100),
            maximum=estimated_max
        )

    async def _read_battle_list(self, frame: np.ndarray):
        """
        Read the battle list to detect creatures and players.

        For Tibia, the battle list shows:
        - Creature/player name
        - HP bar (percentage)
        - Whether they're attacking you

        Method: Template matching for creature sprites + OCR for names
        """
        region = self.regions["battle_list"]
        battle_region = frame[region["y"]:region["y"]+region["h"],
                              region["x"]:region["x"]+region["w"]]

        if battle_region.size == 0:
            return

        creatures = []

        # If OCR is available, use it for name extraction
        if self._ocr_engine:
            try:
                results = self._ocr_engine.readtext(
                    battle_region,
                    detail=1,
                    paragraph=False,
                )

                for (bbox, text, confidence) in results:
                    if confidence > 0.5 and text.strip():
                        creatures.append(CreatureState(
                            name=text.strip(),
                            hp_percent=100.0,  # Will be refined with HP bar reading
                            distance=0,        # Will be calculated from position
                            is_player=text[0].isupper(),  # Heuristic: player names start uppercase
                            last_seen=time.time(),
                        ))
            except Exception as e:
                log.debug("game_reader.ocr_error", region="battle_list", error=str(e))

        self.state.update_battle_list(creatures)

    async def _read_minimap(self, frame: np.ndarray):
        """
        Read position from the minimap.

        Tibia's minimap shows a top-down view with color-coded terrain.
        Position can be determined by matching minimap patterns against
        a database of known locations.
        """
        region = self.regions["minimap"]
        minimap = frame[region["y"]:region["y"]+region["h"],
                        region["x"]:region["x"]+region["w"]]

        if minimap.size == 0:
            return

        # TODO: Implement minimap position matching
        # This requires a minimap database (can be built from Tibia wiki maps)
        # For now, position updates come from other sources (click tracking)

    async def _read_chat(self, frame: np.ndarray):
        """
        Read chat messages from the chat window.

        Useful for:
        - Server messages (loot, XP gained)
        - Player messages (trade, threats)
        - System warnings
        """
        region = self.regions["chat_window"]
        chat = frame[region["y"]:region["y"]+region["h"],
                     region["x"]:region["x"]+region["w"]]

        if chat.size == 0 or self._ocr_engine is None:
            return

        try:
            results = self._ocr_engine.readtext(chat, detail=1)

            for (bbox, text, confidence) in results:
                if confidence > 0.6:
                    # Parse XP messages: "You gained X experience points."
                    if "experience" in text.lower():
                        self._parse_xp_message(text)
                    # Parse loot messages
                    elif "loot" in text.lower() or "gold" in text.lower():
                        self._parse_loot_message(text)

        except Exception as e:
            log.debug("game_reader.chat_ocr_error", error=str(e))

    def _parse_xp_message(self, text: str):
        """Extract XP value from experience message."""
        import re
        match = re.search(r'(\d[\d,]*)\s*experience', text, re.IGNORECASE)
        if match:
            xp = int(match.group(1).replace(',', ''))
            self.state.session.xp_gained += xp

    def _parse_loot_message(self, text: str):
        """Extract loot value from loot message."""
        import re
        match = re.search(r'(\d[\d,]*)\s*gold', text, re.IGNORECASE)
        if match:
            gold = int(match.group(1).replace(',', ''))
            self.state.session.loot_value += gold
