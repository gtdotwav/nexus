"""
NEXUS Agent - Screen Capture Module

High-performance screen capture optimized for real-time gaming.
Uses dxcam on Windows (DirectX capture) with fallback to mss.
"""

from __future__ import annotations

import asyncio
import threading
import time
import numpy as np
import structlog
from typing import Optional

log = structlog.get_logger()


class ScreenCapture:
    """
    Captures the game screen at high FPS.

    Performance targets:
        - dxcam: <2ms per capture (GPU-accelerated)
        - mss: <5ms per capture (CPU-based fallback)
    """

    def __init__(self, config: dict):
        self.config = config
        self.fps = config["capture"]["fps"]
        self.monitor_index = config["capture"]["monitor_index"]
        self.backend = config["capture"]["backend"]

        self._camera = None
        self._game_window_region = None  # (left, top, right, bottom)
        self._initialized = False
        self._frame_count = 0
        self._fps_timer = time.time()
        self._fps_lock = threading.Lock()  # Thread-safe FPS counter
        self._last_frame: Optional[np.ndarray] = None  # Cached for vision loop

    @property
    def last_frame(self) -> Optional[np.ndarray]:
        """Most recently captured frame. Used by vision loop for passive observation."""
        return self._last_frame

    async def initialize(self):
        """Initialize the screen capture backend."""
        try:
            if self.backend == "dxcam":
                await self._init_dxcam()
            else:
                await self._init_mss()

            self._initialized = True
            log.info(
                "screen_capture.initialized",
                backend=self.backend,
                target_fps=self.fps,
            )
        except ImportError as e:
            log.warning("screen_capture.fallback", reason=str(e), fallback="mss")
            self.backend = "mss"
            await self._init_mss()
            self._initialized = True

    async def _init_dxcam(self):
        """Initialize dxcam (Windows DirectX capture)."""
        import dxcam

        self._camera = dxcam.create(
            device_idx=0,
            output_idx=self.monitor_index,
            output_color="BGR",  # OpenCV compatible
        )
        log.info("screen_capture.dxcam_ready")

    async def _init_mss(self):
        """Initialize mss (cross-platform fallback)."""
        import mss

        self._camera = mss.mss()
        log.info("screen_capture.mss_ready")

    async def capture(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the game window.

        Returns:
            numpy array (BGR format) or None if capture failed.
        """
        if not self._initialized:
            return None

        try:
            if self.backend == "dxcam":
                frame = await self._capture_dxcam()
            else:
                frame = await self._capture_mss()

            # Cache frame for vision loop
            if frame is not None:
                self._last_frame = frame

            # Track FPS (thread-safe)
            with self._fps_lock:
                self._frame_count += 1
                elapsed = time.time() - self._fps_timer
                if elapsed >= 5.0:  # Log FPS every 5 seconds
                    actual_fps = self._frame_count / elapsed
                    log.debug("screen_capture.fps", actual=round(actual_fps, 1), target=self.fps)
                    self._frame_count = 0
                    self._fps_timer = time.time()

            return frame

        except Exception as e:
            log.error("screen_capture.error", error=str(e))
            return None

    async def _capture_dxcam(self) -> Optional[np.ndarray]:
        """Capture using dxcam."""
        if self._game_window_region:
            frame = self._camera.grab(region=self._game_window_region)
        else:
            frame = self._camera.grab()
        return frame

    async def _capture_mss(self) -> Optional[np.ndarray]:
        """Capture using mss."""
        import mss
        import numpy as np

        monitor = self._camera.monitors[self.monitor_index + 1]  # mss uses 1-indexed

        if self._game_window_region:
            left, top, right, bottom = self._game_window_region
            monitor = {
                "left": left,
                "top": top,
                "width": right - left,
                "height": bottom - top,
            }

        screenshot = self._camera.grab(monitor)
        frame = np.array(screenshot)
        # mss returns BGRA, convert to BGR
        return frame[:, :, :3]

    def set_game_window(self, left: int, top: int, right: int, bottom: int):
        """Set the game window region for targeted capture."""
        self._game_window_region = (left, top, right, bottom)
        log.info(
            "screen_capture.window_set",
            region=self._game_window_region,
            width=right - left,
            height=bottom - top,
        )

    async def find_game_window(self, window_title: str = "Tibia") -> bool:
        """
        Automatically find the game window by title.
        Cross-platform: uses ctypes on Windows, Quartz on macOS.
        """
        import sys

        if sys.platform == "win32":
            return await self._find_window_windows(window_title)
        elif sys.platform == "darwin":
            return await self._find_window_macos(window_title)
        else:
            log.warning("screen_capture.find_window_unsupported", platform=sys.platform)
            return False

    async def _find_window_windows(self, window_title: str) -> bool:
        """Find game window on Windows using ctypes/win32."""
        try:
            import ctypes
            import ctypes.wintypes

            hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
            if not hwnd:
                log.warning("screen_capture.window_not_found", title=window_title)
                return False

            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

            self.set_game_window(rect.left, rect.top, rect.right, rect.bottom)
            log.info("screen_capture.window_found", title=window_title, hwnd=hwnd)
            return True

        except Exception as e:
            log.error("screen_capture.find_window_error", error=str(e))
            return False

    async def _find_window_macos(self, window_title: str) -> bool:
        """Find game window on macOS using Quartz (CoreGraphics)."""
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID,
            )

            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )

            for window in window_list:
                name = window.get("kCGWindowName", "")
                owner = window.get("kCGWindowOwnerName", "")

                # Match by window name or owner (app name)
                if window_title.lower() in str(name).lower() or \
                   window_title.lower() in str(owner).lower():
                    bounds = window.get("kCGWindowBounds", {})
                    x = int(bounds.get("X", 0))
                    y = int(bounds.get("Y", 0))
                    w = int(bounds.get("Width", 0))
                    h = int(bounds.get("Height", 0))

                    if w > 100 and h > 100:  # Skip tiny windows (menus, etc.)
                        self.set_game_window(x, y, x + w, y + h)
                        log.info("screen_capture.window_found",
                                 title=name or owner,
                                 owner=owner,
                                 bounds=f"{w}x{h}+{x}+{y}")
                        return True

            log.warning("screen_capture.window_not_found", title=window_title)
            return False

        except ImportError:
            log.warning("screen_capture.quartz_not_available",
                        hint="Install pyobjc-framework-Quartz: pip install pyobjc-framework-Quartz")
            return False
        except Exception as e:
            log.error("screen_capture.find_window_error", error=str(e))
            return False

    def extract_region(self, frame: np.ndarray, region: dict) -> Optional[np.ndarray]:
        """
        Extract a specific region from a captured frame.

        Args:
            frame: Full game screen frame
            region: Dict with x, y, w, h keys

        Returns:
            Cropped frame region
        """
        if frame is None:
            return None

        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        return frame[y:y+h, x:x+w].copy()
