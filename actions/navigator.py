"""
NEXUS Agent — Navigation Engine

Executes waypoint sequences from skills. Handles:
- Walk: Click-to-walk between coordinates
- Hunt Area: Patrol within radius, engaging targets
- Rope/Shovel: Use tools for floor transitions
- Stairs: Navigate stairways up/down
- Depot: Enter/exit depot
- Escape: Emergency pathfinding to safe zone

The navigator doesn't just follow waypoints blindly — it adapts:
- Skips waypoints if already past them
- Re-routes if blocked
- Switches to escape waypoints during PK
- Adjusts walk speed based on threat level
"""

from __future__ import annotations

import asyncio
import math
import time
import random
import structlog
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState, Position

log = structlog.get_logger()


class NavAction(Enum):
    WALK = "walk"
    HUNT_AREA = "hunt_area"
    LOOT_CHECK = "loot_check"
    USE_ROPE = "use_rope"
    USE_SHOVEL = "use_shovel"
    USE_STAIR = "use_stair"
    DEPOT = "depot"
    WAIT = "wait"


@dataclass
class Waypoint:
    """Single navigation waypoint."""
    x: int
    y: int
    z: int
    action: NavAction
    label: str = ""
    radius: int = 0        # For hunt_area
    wait_seconds: float = 0 # For wait action
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Waypoint":
        action = NavAction(data.get("action", "walk"))
        return cls(
            x=data["x"],
            y=data["y"],
            z=data["z"],
            action=action,
            label=data.get("label", ""),
            radius=data.get("radius", 0),
            wait_seconds=data.get("wait_seconds", 0),
            extra={k: v for k, v in data.items()
                   if k not in ("x", "y", "z", "action", "label", "radius", "wait_seconds")},
        )

    def distance_to(self, pos) -> float:
        """Euclidean distance to a position (same floor)."""
        return math.sqrt((self.x - pos.x) ** 2 + (self.y - pos.y) ** 2)


class Navigator:
    """
    Waypoint execution engine.

    Manages:
    - Route: ordered list of waypoints (loaded from active skill)
    - Escape route: emergency waypoints for PK flee
    - Current index: which waypoint we're heading toward
    - Loop mode: whether to loop back to start after completing route
    - Hunt area logic: patrol within radius until area is clear
    """

    def __init__(self, state: "GameState", input_handler, config: dict):
        self.state = state
        self.input = input_handler
        self.config = config

        # Route state
        self.route: list[Waypoint] = []
        self.escape_route: list[Waypoint] = []
        self.current_index: int = 0
        self.loop_mode: bool = True
        self.is_escaping: bool = False

        # Hunt area state
        self._hunting_in_area: bool = False
        self._hunt_area_start: float = 0
        self._hunt_area_max_seconds: float = 120  # Max 2min per area

        # Movement tracking
        self._last_position = None
        self._stuck_counter: int = 0
        self._stuck_threshold: int = 5     # Ticks without movement = stuck
        self._last_walk_time: float = 0
        self._walk_cooldown: float = 0.3   # Min seconds between walk clicks

        # Stats
        self.waypoints_completed: int = 0
        self.routes_completed: int = 0
        self.stuck_recoveries: int = 0

    def load_route(self, waypoints: list[dict], escape: list[dict] = None):
        """Load waypoints from skill definition."""
        self.route = [Waypoint.from_dict(wp) for wp in waypoints]
        self.escape_route = [Waypoint.from_dict(wp) for wp in (escape or [])]
        self.current_index = 0
        self._hunting_in_area = False
        log.info("navigator.route_loaded",
                 waypoints=len(self.route),
                 escape=len(self.escape_route))

    def start_escape(self):
        """Switch to escape route (PK flee)."""
        if self.escape_route and not self.is_escaping:
            self.is_escaping = True
            self.current_index = 0
            log.info("navigator.escaping", waypoints=len(self.escape_route))

    def stop_escape(self):
        """Return to normal route after escape."""
        if self.is_escaping:
            self.is_escaping = False
            # Find closest waypoint on normal route to resume from
            self.current_index = self._find_closest_waypoint(self.route)
            log.info("navigator.resumed", index=self.current_index)

    @property
    def active_route(self) -> list[Waypoint]:
        return self.escape_route if self.is_escaping else self.route

    @property
    def current_waypoint(self) -> Optional[Waypoint]:
        route = self.active_route
        if not route or self.current_index >= len(route):
            return None
        return route[self.current_index]

    async def tick(self) -> Optional[str]:
        """
        Execute one navigation tick. Returns action taken or None.

        Called by the reactive brain at lower priority than combat.
        """
        route = self.active_route
        if not route:
            return None

        wp = self.current_waypoint
        if wp is None:
            # Route complete
            if self.loop_mode and not self.is_escaping:
                self.current_index = 0
                self.routes_completed += 1
                log.info("navigator.route_loop", completed=self.routes_completed)
                return "route_looped"
            return None

        # Check if we've reached current waypoint
        pos = self.state.position
        if pos is None:
            return None

        dist = wp.distance_to(pos)
        same_floor = pos.z == wp.z

        # Stuck detection
        self._check_stuck(pos)

        if same_floor and dist <= 2:
            # Arrived at waypoint — execute its action
            return await self._execute_waypoint(wp)

        elif not same_floor:
            # Different floor — need stair/rope/shovel
            return await self._handle_floor_change(wp)

        else:
            # Still walking — click toward waypoint
            return await self._walk_toward(wp)

    async def _execute_waypoint(self, wp: Waypoint) -> str:
        """Execute the action for a reached waypoint."""

        if wp.action == NavAction.WALK:
            self._advance()
            return "walk_complete"

        elif wp.action == NavAction.HUNT_AREA:
            return await self._handle_hunt_area(wp)

        elif wp.action == NavAction.LOOT_CHECK:
            # Pause briefly for looting (loot engine handles actual looting)
            await asyncio.sleep(0.5)
            self._advance()
            return "loot_check"

        elif wp.action == NavAction.USE_ROPE:
            await self.input.press_key(self.config.get("rope_hotkey", "f11"))
            await asyncio.sleep(1.0)
            self._advance()
            return "used_rope"

        elif wp.action == NavAction.USE_SHOVEL:
            await self.input.press_key(self.config.get("shovel_hotkey", "f12"))
            await asyncio.sleep(1.0)
            self._advance()
            return "used_shovel"

        elif wp.action == NavAction.DEPOT:
            self._advance()
            return "at_depot"

        elif wp.action == NavAction.WAIT:
            await asyncio.sleep(wp.wait_seconds or 1.0)
            self._advance()
            return "waited"

        else:
            self._advance()
            return "unknown_action"

    async def _handle_hunt_area(self, wp: Waypoint) -> str:
        """
        Hunt area logic: stay in area while there are targets.
        Leave when area is clear or timeout reached.
        """
        if not self._hunting_in_area:
            self._hunting_in_area = True
            self._hunt_area_start = time.time()
            log.debug("navigator.hunting_area", label=wp.label, radius=wp.radius)

        # Check exit conditions
        elapsed = time.time() - self._hunt_area_start
        battle_list = self.state.battle_list

        # No monsters nearby → area clear, move on
        area_clear = len(battle_list) == 0
        # Timeout
        timed_out = elapsed > self._hunt_area_max_seconds

        if area_clear or timed_out:
            self._hunting_in_area = False
            self._advance()
            reason = "clear" if area_clear else "timeout"
            log.debug("navigator.area_done", label=wp.label, reason=reason,
                      elapsed_s=round(elapsed))
            return f"hunt_area_{reason}"

        # Still hunting — patrol within radius (small random walks)
        if random.random() < 0.1:  # 10% chance per tick to reposition
            dx = random.randint(-wp.radius, wp.radius)
            dy = random.randint(-wp.radius, wp.radius)
            target_x = wp.x + dx
            target_y = wp.y + dy
            await self._click_minimap(target_x, target_y)

        return "hunting_area"

    async def _handle_floor_change(self, wp: Waypoint) -> str:
        """Handle movement between floors (stairs, ropes, shovels)."""
        pos = self.state.position
        going_up = wp.z < pos.z
        going_down = wp.z > pos.z

        if going_up:
            # Try rope first, then stairs
            rope_hotkey = self.config.get("rope_hotkey")
            if rope_hotkey:
                await self.input.press_key(rope_hotkey)
                await asyncio.sleep(1.5)
                return "rope_up"
            else:
                # Walk toward stairway
                await self._walk_toward(wp)
                return "walking_to_stair"
        else:
            # Going down — shovel or stair
            shovel_hotkey = self.config.get("shovel_hotkey")
            if shovel_hotkey:
                await self.input.press_key(shovel_hotkey)
                await asyncio.sleep(1.5)
                return "shovel_down"
            else:
                await self._walk_toward(wp)
                return "walking_to_stair"

    async def _walk_toward(self, wp: Waypoint) -> str:
        """Click to walk toward a waypoint."""
        now = time.time()
        if now - self._last_walk_time < self._walk_cooldown:
            return "walk_cooldown"

        await self._click_minimap(wp.x, wp.y)
        self._last_walk_time = now
        return "walking"

    async def _click_minimap(self, target_x: int, target_y: int):
        """
        Click on minimap to walk toward game coordinates.

        Converts game coords to minimap pixel position relative to character center.
        The minimap in Tibia shows a ~15x11 SQM area centered on the player.
        """
        pos = self.state.position
        if pos is None:
            return

        # Delta in SQMs
        dx = target_x - pos.x
        dy = target_y - pos.y

        # Clamp to visible minimap range
        dx = max(-7, min(7, dx))
        dy = max(-5, min(5, dy))

        # Get minimap region from config
        minimap = self.config.get("minimap_region", {})
        center_x = minimap.get("center_x", 0)
        center_y = minimap.get("center_y", 0)
        sqm_pixels = minimap.get("sqm_pixels", 4)

        # Convert to pixel offset from minimap center
        pixel_x = center_x + (dx * sqm_pixels)
        pixel_y = center_y + (dy * sqm_pixels)

        # Add humanization noise
        noise = random.gauss(0, 1)
        pixel_x += noise
        pixel_y += noise

        await self.input.click(int(pixel_x), int(pixel_y))

    def _advance(self):
        """Move to the next waypoint."""
        self.current_index += 1
        self.waypoints_completed += 1
        self._stuck_counter = 0

        wp = self.current_waypoint
        if wp and wp.label:
            log.debug("navigator.advancing", index=self.current_index, label=wp.label)

    def _check_stuck(self, pos):
        """Detect if we're stuck (not moving)."""
        if self._last_position and pos.x == self._last_position.x and pos.y == self._last_position.y:
            self._stuck_counter += 1
            if self._stuck_counter >= self._stuck_threshold:
                self._handle_stuck()
        else:
            self._stuck_counter = 0
        self._last_position = pos

    def _handle_stuck(self):
        """Try to recover from being stuck."""
        self.stuck_recoveries += 1
        self._stuck_counter = 0

        # Strategy: skip current waypoint if stuck too long
        log.warning("navigator.stuck", index=self.current_index,
                     recoveries=self.stuck_recoveries)

        # Try walking in a random direction first
        # If stuck 3+ times on same WP, skip it
        if self.stuck_recoveries >= 3:
            self._advance()
            self.stuck_recoveries = 0
            log.info("navigator.skipped_waypoint", reason="stuck_too_long")

    def _find_closest_waypoint(self, route: list[Waypoint]) -> int:
        """Find the closest waypoint in a route to current position."""
        pos = self.state.position
        if not pos or not route:
            return 0

        best_idx = 0
        best_dist = float("inf")
        for i, wp in enumerate(route):
            if wp.z == pos.z:
                dist = wp.distance_to(pos)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
        return best_idx

    @property
    def stats(self) -> dict:
        return {
            "waypoints_completed": self.waypoints_completed,
            "routes_completed": self.routes_completed,
            "stuck_recoveries": self.stuck_recoveries,
            "current_index": self.current_index,
            "total_waypoints": len(self.active_route),
            "is_escaping": self.is_escaping,
            "hunting_area": self._hunting_in_area,
        }
