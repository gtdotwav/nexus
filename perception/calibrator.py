"""
NEXUS — Screen Region Calibrator

Auto-detects UI element positions in the Tibia client.

Why this is needed:
    The HP bar, mana bar, battle list, minimap, etc. are at different
    pixel coordinates depending on:
    - Screen resolution (1920x1080 vs 2560x1440 vs etc.)
    - Tibia client version (12.x vs 13.x)
    - Client window size (fullscreen vs windowed)
    - UI scaling settings

Methods:
    1. TEMPLATE MATCHING: For elements with known visual patterns
       (minimap border, HP/mana bar frame, battle list header)
    2. COLOR ZONE DETECTION: Find red bar (HP), blue bar (mana)
       by scanning for characteristic color patterns
    3. EDGE DETECTION: Find UI panel boundaries using Canny edges
    4. MANUAL FALLBACK: User clicks corners of each region

The calibrator runs ONCE at startup and saves results to config.
"""

from __future__ import annotations

import time
import numpy as np
import cv2
import structlog
from typing import Optional
from dataclasses import dataclass

log = structlog.get_logger()


@dataclass
class CalibratedRegion:
    """A detected UI region with confidence score."""
    name: str
    x: int
    y: int
    w: int
    h: int
    confidence: float = 0.0
    method: str = "unknown"


class ScreenCalibrator:
    """
    Auto-detects Tibia UI element positions from a screenshot.

    Usage:
        calibrator = ScreenCalibrator()
        frame = await screen_capture.capture()
        regions = calibrator.auto_detect(frame)
        # regions = {"hp_bar": {x, y, w, h}, "mana_bar": {...}, ...}
    """

    # Known Tibia UI color signatures
    # HP bar frame: dark gray border around red fill
    HP_BAR_FRAME_COLOR = (50, 50, 50)  # BGR - dark gray frame
    HP_BAR_FILL_COLOR_RANGE = ((0, 0, 120), (80, 80, 255))  # BGR - red fill
    MANA_BAR_FILL_COLOR_RANGE = ((120, 0, 0), (255, 80, 80))  # BGR - blue fill

    # Minimap has a very distinctive border color in Tibia
    MINIMAP_BORDER_COLOR_RANGE = ((40, 40, 40), (80, 80, 80))  # Dark gray border

    def __init__(self):
        self._detected_regions: dict[str, CalibratedRegion] = {}

    def auto_detect(self, frame: np.ndarray) -> dict[str, dict]:
        """
        Auto-detect all UI regions from a single game screenshot.

        Returns dict of region_name → {x, y, w, h} ready for config.
        """
        if frame is None:
            return {}

        h, w = frame.shape[:2]
        log.info("calibrator.starting", frame_size=f"{w}x{h}")

        results = {}

        # 1. Detect HP bar (red horizontal bar in top-left area)
        hp_region = self._find_hp_bar(frame)
        if hp_region:
            results["hp_bar"] = hp_region
            log.info("calibrator.found_hp_bar", **hp_region)

        # 2. Detect Mana bar (blue bar, usually right below HP)
        mana_region = self._find_mana_bar(frame, hp_region)
        if mana_region:
            results["mana_bar"] = mana_region
            log.info("calibrator.found_mana_bar", **mana_region)

        # 3. Detect battle list (right side panel with creature entries)
        battle_region = self._find_battle_list(frame)
        if battle_region:
            results["battle_list"] = battle_region
            log.info("calibrator.found_battle_list", **battle_region)

        # 4. Detect minimap (top-right square with colored terrain)
        minimap_region = self._find_minimap(frame)
        if minimap_region:
            results["minimap"] = minimap_region
            log.info("calibrator.found_minimap", **minimap_region)

        # 5. Estimate game screen (the central viewport)
        game_screen = self._estimate_game_screen(frame, results)
        if game_screen:
            results["game_screen"] = game_screen

        log.info("calibrator.complete", regions_found=len(results),
                 names=list(results.keys()))

        return results

    def _find_hp_bar(self, frame: np.ndarray) -> Optional[dict]:
        """
        Find HP bar by scanning for a horizontal colored bar in the top-left quadrant.

        Tibia HP bar characteristics:
        - Located in top 30% of screen
        - Located in left 50% of screen
        - Horizontal bar, typically 100-200px wide, 8-15px tall
        - Color changes with HP level:
            * GREEN when HP is high (G > 120, G > R+40, G > B+40)
            * YELLOW/ORANGE at medium HP
            * RED when HP is low (R > 120, R > G+40, R > B+40)
        - We detect ALL these colors to find the bar regardless of current HP
        """
        h, w = frame.shape[:2]
        # Scan top-left quadrant only
        search_region = frame[:int(h * 0.3), :int(w * 0.5)]

        r = search_region[:, :, 2].astype(np.int16)
        g = search_region[:, :, 1].astype(np.int16)
        b = search_region[:, :, 0].astype(np.int16)

        # Detect ALL possible HP bar colors:
        # Green (full HP): G dominant
        green_mask = (g > 120) & (g > r + 30) & (g > b + 30)
        # Red (low HP): R dominant
        red_mask = (r > 120) & (r > g + 30) & (r > b + 30)
        # Yellow/Orange (medium HP): R and G both high, B low
        yellow_mask = (r > 100) & (g > 80) & (b < 80) & (r + g > 250)

        # Combined: any HP bar colored pixel
        hp_bar_mask = (green_mask | red_mask | yellow_mask).astype(np.uint8) * 255

        # Find contours of colored regions
        contours, _ = cv2.findContours(hp_bar_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Find the most bar-shaped contour (wide, thin)
        best = None
        best_score = 0
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / max(ch, 1)
            area = cw * ch

            # HP bar should be wide and thin (aspect > 5) and reasonably sized
            if aspect > 4 and 60 < cw < 400 and 4 < ch < 25 and area > 300:
                score = area * aspect  # Prefer wider, thinner bars
                if score > best_score:
                    best_score = score
                    best = {"x": x, "y": y, "w": cw, "h": ch}

        return best

    def _find_mana_bar(self, frame: np.ndarray, hp_region: Optional[dict]) -> Optional[dict]:
        """
        Find mana bar (blue/purple bar, usually directly below HP bar).
        """
        h, w = frame.shape[:2]

        # If we found HP bar, look right below it
        if hp_region:
            search_y_start = hp_region["y"] + hp_region["h"]
            search_y_end = min(search_y_start + 40, h)  # Within 40px below HP
            search_x_start = max(0, hp_region["x"] - 20)
            search_x_end = min(hp_region["x"] + hp_region["w"] + 20, w)
        else:
            search_y_start = 0
            search_y_end = int(h * 0.3)
            search_x_start = 0
            search_x_end = int(w * 0.5)

        search_region = frame[search_y_start:search_y_end, search_x_start:search_x_end]
        if search_region.size == 0:
            return None

        # Mana bar is blue/purple — B channel dominant
        r = search_region[:, :, 2].astype(np.int16)
        g = search_region[:, :, 1].astype(np.int16)
        b = search_region[:, :, 0].astype(np.int16)
        blue_mask = ((b > 100) & (b > r + 30) & (b > g + 30)).astype(np.uint8) * 255

        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_score = 0
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / max(ch, 1)
            area = cw * ch

            if aspect > 4 and 60 < cw < 400 and 4 < ch < 25 and area > 300:
                score = area * aspect
                if score > best_score:
                    best_score = score
                    best = {
                        "x": search_x_start + x,
                        "y": search_y_start + y,
                        "w": cw, "h": ch,
                    }

        return best

    def _find_battle_list(self, frame: np.ndarray) -> Optional[dict]:
        """
        Find battle list by looking for the panel on the right side
        with multiple small horizontal HP bars (creature entries).

        The battle list is typically:
        - Right side of screen (right 30%)
        - Contains multiple small green/yellow/red bars
        - Panel width ~150-200px
        """
        h, w = frame.shape[:2]
        # Scan right 40% of screen
        search_x_start = int(w * 0.6)
        search_region = frame[:, search_x_start:]

        if search_region.size == 0:
            return None

        # Look for columns with many small colored bars
        # Convert to HSV to find saturated (colored) pixels
        hsv = cv2.cvtColor(search_region, cv2.COLOR_BGR2HSV)
        colored_mask = (hsv[:, :, 1] > 80).astype(np.uint8) * 255

        # Find vertical strips with high density of colored pixels
        col_density = np.sum(colored_mask, axis=0) / (h * 255)

        # Find region where density is consistently high (battle list panel)
        threshold = 0.05
        high_density_cols = col_density > threshold
        if not np.any(high_density_cols):
            return None

        # Find contiguous region of high density
        changes = np.diff(high_density_cols.astype(int))
        starts = np.where(changes == 1)[0]
        ends = np.where(changes == -1)[0]

        if len(starts) == 0:
            return None

        # Take the widest contiguous region
        if len(ends) == 0:
            ends = np.array([len(col_density) - 1])
        if starts[0] > ends[0]:
            starts = np.insert(starts, 0, 0)

        best_width = 0
        best_start = 0
        best_end = 0
        for s, e in zip(starts, ends):
            width = e - s
            if 100 < width < 300 and width > best_width:
                best_width = width
                best_start = s
                best_end = e

        if best_width == 0:
            return None

        return {
            "x": search_x_start + best_start,
            "y": int(h * 0.15),  # Skip top header area
            "w": best_width,
            "h": int(h * 0.5),  # Battle list is typically top half
        }

    def _find_minimap(self, frame: np.ndarray) -> Optional[dict]:
        """
        Find minimap by looking for a roughly square colored region
        in the top-right area with terrain-like colors (green, brown, blue).
        """
        h, w = frame.shape[:2]
        # Minimap is typically in the top-right corner
        search_x_start = int(w * 0.7)
        search_region = frame[:int(h * 0.3), search_x_start:]

        if search_region.size == 0:
            return None

        # Minimap has many distinct colors (terrain). Calculate color variance.
        hsv = cv2.cvtColor(search_region, cv2.COLOR_BGR2HSV)

        # Look for square-ish region with high hue variance (many terrain colors)
        block_size = 10
        sh, sw = search_region.shape[:2]

        best_score = 0
        best_region = None

        # Scan with 20px steps for efficiency
        for by in range(0, sh - 80, 20):
            for bx in range(0, sw - 80, 20):
                # Test different minimap sizes (80-130px square)
                for size in [80, 100, 110, 120]:
                    if by + size > sh or bx + size > sw:
                        continue

                    block = hsv[by:by + size, bx:bx + size]
                    hue_std = np.std(block[:, :, 0])
                    sat_mean = np.mean(block[:, :, 1])

                    # Minimap has high hue variety and moderate saturation
                    score = hue_std * sat_mean / 100
                    if score > best_score and hue_std > 20:
                        best_score = score
                        best_region = {
                            "x": search_x_start + bx,
                            "y": by,
                            "w": size,
                            "h": size,
                        }

        return best_region

    def _estimate_game_screen(self, frame: np.ndarray, found: dict) -> Optional[dict]:
        """Estimate the main game viewport based on other detected regions."""
        h, w = frame.shape[:2]

        # Game screen is typically the large central area
        left = 0
        top = 0

        # If we found HP bar, game screen starts below it
        if "hp_bar" in found:
            hp = found["hp_bar"]
            top = max(top, hp["y"] + hp["h"] + 5)

        # If we found mana bar, game screen starts below it
        if "mana_bar" in found:
            mana = found["mana_bar"]
            top = max(top, mana["y"] + mana["h"] + 5)

        # Right edge: before battle list or minimap
        right = w
        if "battle_list" in found:
            right = min(right, found["battle_list"]["x"] - 5)
        if "minimap" in found:
            right = min(right, found["minimap"]["x"] - 5)

        return {
            "x": left,
            "y": top,
            "w": right - left,
            "h": int(h * 0.7) - top,  # Leave room for chat at bottom
        }

    def get_minimap_center(self, regions: dict) -> dict:
        """
        Calculate the minimap center pixel coordinates.
        Needed by Navigator for click-to-walk conversion.
        """
        if "minimap" not in regions:
            return {}

        mm = regions["minimap"]
        return {
            "center_x": mm["x"] + mm["w"] // 2,
            "center_y": mm["y"] + mm["h"] // 2,
            "sqm_pixels": 4,  # Default Tibia minimap scale
        }
