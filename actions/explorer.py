"""
NEXUS Agent — Explorer Engine

Autonomous exploration of unknown territory.
This is what makes NEXUS able to handle new dungeons, map updates,
and areas it has NEVER been programmed for.

Exploration Strategies:
    1. FRONTIER — Move toward boundary of known/unknown
    2. DEEP    — Push deeper into a dungeon (prioritize stairs down)
    3. SWEEP   — Systematically clear-explore an area
    4. VALUE   — Explore toward high-value signals (creature density, loot)
    5. SAFE    — Explore only low-danger areas (for learning)
    6. RETURN  — Navigate back to known safe territory

The explorer works WITH the navigator, not replacing it.
When exploring, it generates dynamic waypoints that the navigator follows.
When the area is sufficiently mapped, it converts to a proper skill.
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
    from core.state import GameState
    from perception.spatial_memory import SpatialMemory
    from actions.navigator import Navigator

log = structlog.get_logger()


class ExploreStrategy(Enum):
    FRONTIER = auto()      # Expand into the unknown
    DEEP = auto()          # Go deeper (find stairs down)
    SWEEP = auto()         # Systematic area coverage
    VALUE = auto()         # Chase high-value signals
    SAFE = auto()          # Conservative exploration
    RETURN = auto()        # Navigate back to safety
    IDLE = auto()          # Not exploring


@dataclass
class ExplorationTarget:
    """A target point to explore."""
    x: int
    y: int
    z: int
    priority: float = 0.0
    reason: str = ""
    strategy: ExploreStrategy = ExploreStrategy.FRONTIER


class Explorer:
    """
    Autonomous exploration engine.

    When NEXUS encounters unknown territory (no skill waypoints, new area),
    the explorer takes over:
    1. Analyzes spatial memory for frontiers
    2. Selects best exploration target based on strategy
    3. Generates dynamic path to target
    4. Walks the path while recording observations
    5. Evaluates results and adjusts strategy
    6. Repeats until area is sufficiently mapped

    The explorer is the bridge between "NEXUS needs a skill for this area"
    and "NEXUS can create one by exploring first."
    """

    def __init__(self, state: "GameState", spatial_memory: "SpatialMemory",
                 navigator: "Navigator", config: dict):
        self.state = state
        self.memory = spatial_memory
        self.navigator = navigator
        self.config = config

        # Exploration state
        self.strategy: ExploreStrategy = ExploreStrategy.IDLE
        self.active: bool = False
        self.current_target: Optional[ExplorationTarget] = None
        self._path: list[tuple[int, int]] = []
        self._path_index: int = 0

        # Strategy parameters
        self._explore_radius: int = 30        # How far from start to explore
        self._safe_hp_threshold: float = 40   # Retreat if HP below this
        self._max_deaths_before_retreat: int = 2
        self._session_deaths: int = 0

        # Tracking
        self._explore_start_time: float = 0
        self._start_position: Optional[tuple[int, int, int]] = None
        self._targets_reached: int = 0
        self._areas_discovered: int = 0

        # Dynamic waypoints generated during exploration
        self.discovered_waypoints: list[dict] = []
        # Observations to feed to strategic brain
        self.observations: list[str] = []

    def start_exploration(self, strategy: ExploreStrategy = ExploreStrategy.FRONTIER,
                           reason: str = "unknown_area"):
        """Begin autonomous exploration."""
        self.active = True
        self.strategy = strategy
        self._explore_start_time = time.time()

        pos = self.state.position
        if pos:
            self._start_position = (pos.x, pos.y, pos.z)

        self._session_deaths = 0
        self.discovered_waypoints = []
        self.observations = []

        log.info("explorer.started",
                 strategy=strategy.name,
                 reason=reason,
                 start_pos=self._start_position)

    def stop_exploration(self) -> dict:
        """Stop exploring and return findings."""
        self.active = False
        old_strategy = self.strategy
        self.strategy = ExploreStrategy.IDLE

        elapsed = time.time() - self._explore_start_time
        findings = {
            "strategy": old_strategy.name,
            "duration_s": round(elapsed, 1),
            "targets_reached": self._targets_reached,
            "areas_discovered": self._areas_discovered,
            "waypoints_generated": len(self.discovered_waypoints),
            "observations": self.observations[-10:],
            "map_stats": self.memory.stats,
        }

        log.info("explorer.stopped", **findings)
        return findings

    async def tick(self) -> Optional[str]:
        """
        One exploration tick. Returns action taken or None.

        Called by the action loop when exploration is active.
        """
        if not self.active:
            return None

        pos = self.state.position
        if pos is None:
            return None

        # Safety checks
        if self._should_retreat():
            self.strategy = ExploreStrategy.RETURN
            self.observations.append(
                f"Retreating — HP={self.state.hp_percent:.0f}%, "
                f"deaths={self._session_deaths}"
            )

        # Record observation (passive mapping happens via spatial_memory)
        self.memory.observe_position(pos.x, pos.y, pos.z)

        # Do we have a target?
        if self.current_target is None or self._reached_target():
            if self.current_target and self._reached_target():
                self._targets_reached += 1
                self._record_waypoint(pos.x, pos.y, pos.z)

            # Select next target
            self.current_target = self._select_target()
            if self.current_target is None:
                # Nothing to explore
                self.observations.append("No more exploration targets found")
                return "no_targets"

            # Pathfind to target
            self._path = self.memory.find_path(
                pos.x, pos.y,
                self.current_target.x, self.current_target.y,
                pos.z,
                avoid_danger=(self.strategy != ExploreStrategy.DEEP),
            )
            self._path_index = 0

            if not self._path:
                # No known path — walk directly (explore the unknown)
                return await self._walk_toward_unknown()

            log.debug("explorer.new_target",
                       target=f"({self.current_target.x},{self.current_target.y})",
                       reason=self.current_target.reason,
                       path_length=len(self._path))

        # Follow path
        return await self._follow_path()

    async def _follow_path(self) -> str:
        """Follow the computed path step by step."""
        if not self._path or self._path_index >= len(self._path):
            self.current_target = None
            return "path_complete"

        next_pos = self._path[self._path_index]

        # Check if we're close enough to advance to next step
        pos = self.state.position
        dx = next_pos[0] - pos.x
        dy = next_pos[1] - pos.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist <= 2:
            self._path_index += 1
            return "step_complete"

        # Walk toward next path point
        # Convert to arrow key direction
        direction = self._delta_to_direction(dx, dy)
        if direction:
            await self._move(direction)

        return "walking"

    async def _walk_toward_unknown(self) -> str:
        """Walk toward target when no path exists (into unexplored territory)."""
        if self.current_target is None:
            return "no_target"

        pos = self.state.position
        dx = self.current_target.x - pos.x
        dy = self.current_target.y - pos.y

        direction = self._delta_to_direction(dx, dy)
        if direction:
            await self._move(direction)
            return "exploring_unknown"

        return "stuck"

    def _select_target(self) -> Optional[ExplorationTarget]:
        """Select next exploration target based on current strategy."""
        pos = self.state.position
        if pos is None:
            return None

        if self.strategy == ExploreStrategy.RETURN:
            return self._target_return()
        elif self.strategy == ExploreStrategy.FRONTIER:
            return self._target_frontier()
        elif self.strategy == ExploreStrategy.DEEP:
            return self._target_deep()
        elif self.strategy == ExploreStrategy.SWEEP:
            return self._target_sweep()
        elif self.strategy == ExploreStrategy.VALUE:
            return self._target_value()
        elif self.strategy == ExploreStrategy.SAFE:
            return self._target_safe()

        return None

    def _target_frontier(self) -> Optional[ExplorationTarget]:
        """Target the highest-priority frontier cell."""
        pos = self.state.position
        frontiers = self.memory.compute_frontiers(pos.z, max_frontiers=10)

        if not frontiers:
            return None

        # Pick the best frontier within explore radius
        for f in frontiers:
            dx = f["x"] - pos.x
            dy = f["y"] - pos.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist <= self._explore_radius:
                return ExplorationTarget(
                    x=f["x"], y=f["y"], z=f["z"],
                    priority=f["priority"],
                    reason=f"frontier (danger={f['danger']}, value={f['value']})",
                    strategy=ExploreStrategy.FRONTIER,
                )

        return None

    def _target_deep(self) -> Optional[ExplorationTarget]:
        """Target stairs down to go deeper."""
        pos = self.state.position
        stair = self.memory.find_nearest_landmark(pos.x, pos.y, pos.z, "stair_down")

        if stair:
            return ExplorationTarget(
                x=stair[0], y=stair[1], z=stair[2],
                priority=0.9,
                reason=f"stair_down at distance {stair[3]:.0f}",
                strategy=ExploreStrategy.DEEP,
            )

        # No known stairs — fall back to frontier
        return self._target_frontier()

    def _target_sweep(self) -> Optional[ExplorationTarget]:
        """Systematically sweep unexplored cells in a spiral pattern."""
        pos = self.state.position

        # Spiral outward from current position
        for radius in range(3, self._explore_radius, 3):
            for angle_deg in range(0, 360, 30):
                angle = math.radians(angle_deg)
                tx = pos.x + int(radius * math.cos(angle))
                ty = pos.y + int(radius * math.sin(angle))

                if not self.memory.is_explored(tx, ty, pos.z):
                    return ExplorationTarget(
                        x=tx, y=ty, z=pos.z,
                        priority=1.0 - (radius / self._explore_radius),
                        reason=f"sweep r={radius} deg={angle_deg}",
                        strategy=ExploreStrategy.SWEEP,
                    )

        return None

    def _target_value(self) -> Optional[ExplorationTarget]:
        """Target areas with high creature density / loot potential."""
        pos = self.state.position
        frontiers = self.memory.compute_frontiers(pos.z, max_frontiers=20)

        # Filter for high-value frontiers
        high_value = [f for f in frontiers if f["value"] > 0.3]
        if high_value:
            best = max(high_value, key=lambda f: f["value"])
            return ExplorationTarget(
                x=best["x"], y=best["y"], z=best["z"],
                priority=best["value"],
                reason=f"high-value frontier (value={best['value']})",
                strategy=ExploreStrategy.VALUE,
            )

        return self._target_frontier()

    def _target_safe(self) -> Optional[ExplorationTarget]:
        """Explore only low-danger frontiers."""
        pos = self.state.position
        frontiers = self.memory.compute_frontiers(pos.z, max_frontiers=20)

        safe = [f for f in frontiers if f["danger"] < 0.2]
        if safe:
            best = safe[0]  # Already sorted by priority
            return ExplorationTarget(
                x=best["x"], y=best["y"], z=best["z"],
                priority=best["priority"],
                reason=f"safe frontier (danger={best['danger']})",
                strategy=ExploreStrategy.SAFE,
            )

        return None

    def _target_return(self) -> Optional[ExplorationTarget]:
        """Navigate back to start position or nearest depot."""
        pos = self.state.position

        # Try nearest depot first
        depot = self.memory.find_nearest_landmark(pos.x, pos.y, pos.z, "depot")
        if depot:
            return ExplorationTarget(
                x=depot[0], y=depot[1], z=depot[2],
                priority=1.0,
                reason="return to depot",
                strategy=ExploreStrategy.RETURN,
            )

        # Fall back to start position
        if self._start_position:
            sx, sy, sz = self._start_position
            return ExplorationTarget(
                x=sx, y=sy, z=sz,
                priority=0.9,
                reason="return to start",
                strategy=ExploreStrategy.RETURN,
            )

        return None

    def _should_retreat(self) -> bool:
        """Check if NEXUS should retreat from exploration."""
        if self.strategy == ExploreStrategy.RETURN:
            return False

        # HP too low
        if self.state.hp_percent < self._safe_hp_threshold:
            return True

        # Too many deaths
        if self._session_deaths >= self._max_deaths_before_retreat:
            return True

        return False

    def _reached_target(self) -> bool:
        """Check if we've reached the current exploration target."""
        if not self.current_target:
            return False

        pos = self.state.position
        if pos is None:
            return False

        dx = self.current_target.x - pos.x
        dy = self.current_target.y - pos.y
        return (dx * dx + dy * dy) <= 9  # Within 3 tiles

    def _record_waypoint(self, x: int, y: int, z: int):
        """Record a waypoint from exploration for future skill generation."""
        # Determine what kind of waypoint this is
        area_creatures = self.memory.get_creatures_in_area(x, y, z, radius=5)
        danger = self.memory.get_area_danger(x, y, z)

        if area_creatures and danger < 0.5:
            action = "hunt_area"
            radius = 6
        else:
            action = "walk"
            radius = 0

        wp = {
            "x": x, "y": y, "z": z,
            "action": action,
            "radius": radius,
            "label": f"explored_{len(self.discovered_waypoints)}",
            "creatures": area_creatures,
            "danger": round(danger, 2),
        }
        self.discovered_waypoints.append(wp)

    def record_death(self, cause: str = ""):
        """Record an exploration death."""
        self._session_deaths += 1
        pos = self.state.position
        if pos:
            self.observations.append(
                f"Died at ({pos.x},{pos.y},{pos.z}): {cause}. "
                f"Deaths this exploration: {self._session_deaths}"
            )

    async def _move(self, direction: str):
        """Move in a direction using the input handler."""
        from pynput.keyboard import Key, Controller
        key_map = {
            "n": "up", "s": "down", "e": "right", "w": "left",
            "ne": "up", "nw": "up", "se": "down", "sw": "down",
        }
        key = key_map.get(direction, "")
        if key:
            await self.navigator.input.press_key(key)

    def _delta_to_direction(self, dx: int, dy: int) -> str:
        """Convert dx/dy delta to compass direction."""
        if dx == 0 and dy == 0:
            return ""

        # Normalize
        angle = math.atan2(dy, dx)  # radians
        deg = math.degrees(angle) % 360

        # 8-direction mapping
        if deg < 22.5 or deg >= 337.5:
            return "e"
        elif deg < 67.5:
            return "se"
        elif deg < 112.5:
            return "s"
        elif deg < 157.5:
            return "sw"
        elif deg < 202.5:
            return "w"
        elif deg < 247.5:
            return "nw"
        elif deg < 292.5:
            return "n"
        else:
            return "ne"

    def generate_skill_from_exploration(self) -> Optional[dict]:
        """
        Convert exploration findings into a YAML skill definition.
        Called after exploration is complete to create a usable hunting skill.
        """
        if len(self.discovered_waypoints) < 3:
            return None

        # Filter to only hunt_area and walk waypoints
        route_wps = [wp for wp in self.discovered_waypoints
                      if wp["action"] in ("walk", "hunt_area")]

        if not route_wps:
            return None

        # Determine area properties
        all_creatures = {}
        for wp in route_wps:
            for creature, count in wp.get("creatures", {}).items():
                all_creatures[creature] = all_creatures.get(creature, 0) + count

        dominant_creature = max(all_creatures, key=all_creatures.get) if all_creatures else "Unknown"

        avg_z = sum(wp["z"] for wp in route_wps) // len(route_wps)
        avg_x = sum(wp["x"] for wp in route_wps) // len(route_wps)
        avg_y = sum(wp["y"] for wp in route_wps) // len(route_wps)

        skill_data = {
            "name": f"Explored - {dominant_creature} Area ({avg_x},{avg_y},z{avg_z})",
            "game": "tibia",
            "version": "1.0",
            "category": "hunting",
            "performance_score": 50.0,
            "metadata": {
                "description": f"Auto-generated from exploration. "
                               f"Dominant creature: {dominant_creature}",
                "auto_generated": True,
                "exploration_date": time.strftime("%Y-%m-%d"),
                "creatures_found": all_creatures,
            },
            "waypoints": [
                {"x": wp["x"], "y": wp["y"], "z": wp["z"],
                 "action": wp["action"], "label": wp.get("label", ""),
                 "radius": wp.get("radius", 0)}
                for wp in route_wps
            ],
            "targeting": [
                {"name": creature, "priority": i, "stance": "balanced",
                 "attack_mode": "balanced", "chase_mode": True,
                 "loot": True}
                for i, creature in enumerate(sorted(all_creatures, key=all_creatures.get, reverse=True)[:5])
            ],
        }

        log.info("explorer.skill_generated",
                 name=skill_data["name"],
                 waypoints=len(route_wps),
                 creatures=list(all_creatures.keys()))

        return skill_data

    @property
    def stats(self) -> dict:
        return {
            "active": self.active,
            "strategy": self.strategy.name,
            "targets_reached": self._targets_reached,
            "waypoints_discovered": len(self.discovered_waypoints),
            "session_deaths": self._session_deaths,
            "observations": len(self.observations),
        }
