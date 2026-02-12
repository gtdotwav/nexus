"""
DEPRECATED — Use perception/spatial_memory_v2.py instead.
This file is kept for backward compatibility and CI import checks only.

NEXUS Agent — Spatial Memory (Legacy)

A persistent, evolving world map built from exploration.
This is what allows NEXUS to understand and navigate territory
it has NEVER been programmed to handle.

Core concepts:
    - Cell Grid: Every game tile is a cell with properties
    - Fog of War: Unknown vs explored vs currently visible
    - Heat Maps: Death density, loot value, creature frequency, danger level
    - Landmarks: Stairs, doors, teleports, NPCs, depot, temple
    - Zones: Clustered areas with aggregate properties (safe, dangerous, profitable)
    - Frontiers: Boundary between known and unknown — exploration targets
    - Persistence: Full map saved to disk, grows across sessions

The spatial memory is what transforms NEXUS from a waypoint-follower
into a true explorer that builds its own understanding of the world.
"""

from __future__ import annotations

import json
import math
import time
import structlog
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Optional

log = structlog.get_logger()


class CellType(Enum):
    """What kind of tile this is."""
    UNKNOWN = 0
    WALKABLE = 1
    WALL = 2
    WATER = 3
    LAVA = 4
    STAIR_UP = 5
    STAIR_DOWN = 6
    ROPE_HOLE = 7
    SHOVEL_HOLE = 8
    TELEPORT = 9
    DOOR = 10
    LOCKED_DOOR = 11
    DEPOT = 12
    TEMPLE = 13
    NPC = 14
    DANGEROUS = 15      # Learned: creatures here killed me


@dataclass
class MapCell:
    """A single tile in the world map."""
    cell_type: int = 0          # CellType value
    walkable: bool = False
    explored: bool = False
    last_seen: float = 0.0
    visit_count: int = 0

    # Heat map data (accumulates over sessions)
    death_count: int = 0
    damage_taken: float = 0.0   # Total damage received here
    creatures_seen: int = 0     # Total creature sightings
    loot_value: float = 0.0     # Total loot found nearby
    player_sightings: int = 0   # PK danger indicator

    # Landmark info
    landmark: str = ""          # "stair_down", "depot", "npc_rashid", etc.
    landmark_data: dict = field(default_factory=dict)

    # Creature spawns observed at this position
    creature_types: dict = field(default_factory=dict)  # {"Dragon": 5, "Dragon Lord": 2}

    @property
    def danger_score(self) -> float:
        """0-1 danger rating based on accumulated data."""
        score = 0.0
        if self.death_count > 0:
            score += min(0.5, self.death_count * 0.15)
        if self.creatures_seen > 10:
            score += min(0.3, self.creatures_seen * 0.01)
        if self.player_sightings > 0:
            score += min(0.2, self.player_sightings * 0.05)
        return min(1.0, score)

    @property
    def value_score(self) -> float:
        """0-1 value rating (XP + loot potential)."""
        creature_value = min(1.0, self.creatures_seen * 0.02)
        loot_ratio = min(1.0, self.loot_value / 10000) if self.loot_value > 0 else 0
        return (creature_value * 0.6 + loot_ratio * 0.4)


class Floor:
    """A single floor/level of the map (z-coordinate)."""

    def __init__(self, z: int):
        self.z = z
        self.cells: dict[tuple[int, int], MapCell] = {}
        self._min_x = float('inf')
        self._max_x = float('-inf')
        self._min_y = float('inf')
        self._max_y = float('-inf')

    def get(self, x: int, y: int) -> MapCell:
        key = (x, y)
        if key not in self.cells:
            self.cells[key] = MapCell()
        return self.cells[key]

    def set(self, x: int, y: int, cell: MapCell):
        self.cells[(x, y)] = cell
        self._min_x = min(self._min_x, x)
        self._max_x = max(self._max_x, x)
        self._min_y = min(self._min_y, y)
        self._max_y = max(self._max_y, y)

    @property
    def explored_count(self) -> int:
        return sum(1 for c in self.cells.values() if c.explored)

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        if not self.cells:
            return (0, 0, 0, 0)
        return (int(self._min_x), int(self._min_y), int(self._max_x), int(self._max_y))


@dataclass
class Zone:
    """
    A clustered area with aggregate properties.
    Zones emerge from exploration — NEXUS discovers them, not a programmer.
    """
    name: str                         # Auto-generated or learned from chat
    center_x: int = 0
    center_y: int = 0
    z: int = 0
    radius: int = 10
    avg_danger: float = 0.0
    avg_value: float = 0.0
    creature_distribution: dict = field(default_factory=dict)
    total_deaths: int = 0
    total_visits: int = 0
    discovered_session: int = 0
    notes: list = field(default_factory=list)    # Consciousness observations


class SpatialMemory:
    """
    Persistent world map that grows with every session.

    Key behaviors:
    - Passively records everything NEXUS sees (minimap, battle list, chat)
    - Actively discovers patterns (spawn clusters, safe corridors, danger zones)
    - Identifies frontiers (boundaries between known and unknown)
    - Provides pathfinding data for the explorer
    - Persists across sessions (disk-backed)
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir) / "maps"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.floors: dict[int, Floor] = {}
        self.zones: list[Zone] = []
        self.landmarks: dict[str, tuple[int, int, int]] = {}  # name → (x, y, z)

        # Exploration stats
        self.total_cells_explored: int = 0
        self.total_landmarks: int = 0
        self.frontiers: list[tuple[int, int, int]] = []  # (x, y, z) frontier cells
        self._frontier_update_time: float = 0

    async def initialize(self):
        """Load persisted map data from disk."""
        map_file = self.data_dir / "world_map.json"
        if map_file.exists():
            try:
                data = json.loads(map_file.read_text())
                self._deserialize(data)
                log.info("spatial_memory.loaded",
                         floors=len(self.floors),
                         cells=self.total_cells_explored,
                         landmarks=len(self.landmarks),
                         zones=len(self.zones))
            except Exception as e:
                log.error("spatial_memory.load_error", error=str(e))
        else:
            log.info("spatial_memory.fresh_start")

    async def save(self):
        """Persist map data to disk."""
        try:
            data = self._serialize()
            map_file = self.data_dir / "world_map.json"
            map_file.write_text(json.dumps(data, separators=(",", ":")))
            log.info("spatial_memory.saved", cells=self.total_cells_explored)
        except Exception as e:
            log.error("spatial_memory.save_error", error=str(e))

    # ═══════════════════════════════════════════════════════
    #  OBSERVATION — Record what NEXUS sees
    # ═══════════════════════════════════════════════════════

    def observe_position(self, x: int, y: int, z: int, visible_radius: int = 7):
        """
        Record that NEXUS can see this area.
        Called every perception tick with the player's position.
        Marks all cells within visible_radius as explored+walkable.
        """
        floor = self._get_floor(z)

        for dx in range(-visible_radius, visible_radius + 1):
            for dy in range(-visible_radius, visible_radius + 1):
                if dx * dx + dy * dy <= visible_radius * visible_radius:
                    cx, cy = x + dx, y + dy
                    cell = floor.get(cx, cy)
                    if not cell.explored:
                        cell.explored = True
                        self.total_cells_explored += 1
                    cell.last_seen = time.time()
                    cell.visit_count += 1
                    floor.set(cx, cy, cell)

        # Mark player's exact position as definitely walkable
        player_cell = floor.get(x, y)
        player_cell.walkable = True
        player_cell.cell_type = CellType.WALKABLE.value
        floor.set(x, y, player_cell)

    def observe_creature(self, creature_name: str, x: int, y: int, z: int,
                          is_player: bool = False):
        """Record a creature/player sighting at a position."""
        floor = self._get_floor(z)
        cell = floor.get(x, y)
        cell.creatures_seen += 1
        cell.creature_types[creature_name] = cell.creature_types.get(creature_name, 0) + 1
        if is_player:
            cell.player_sightings += 1
        floor.set(x, y, cell)

    def observe_death(self, x: int, y: int, z: int, cause: str = ""):
        """Record a death at this position."""
        floor = self._get_floor(z)
        cell = floor.get(x, y)
        cell.death_count += 1
        cell.cell_type = CellType.DANGEROUS.value
        floor.set(x, y, cell)

        log.info("spatial_memory.death_recorded",
                 pos=f"({x},{y},{z})", deaths_here=cell.death_count, cause=cause)

    def observe_landmark(self, x: int, y: int, z: int,
                          landmark_type: str, data: dict = None):
        """Record a landmark (stair, depot, NPC, teleport, etc.)."""
        floor = self._get_floor(z)
        cell = floor.get(x, y)
        cell.landmark = landmark_type
        cell.landmark_data = data or {}

        # Map landmark type to cell type
        type_map = {
            "stair_up": CellType.STAIR_UP,
            "stair_down": CellType.STAIR_DOWN,
            "rope": CellType.ROPE_HOLE,
            "shovel": CellType.SHOVEL_HOLE,
            "teleport": CellType.TELEPORT,
            "door": CellType.DOOR,
            "depot": CellType.DEPOT,
            "temple": CellType.TEMPLE,
            "npc": CellType.NPC,
        }
        if landmark_type in type_map:
            cell.cell_type = type_map[landmark_type].value

        floor.set(x, y, cell)

        key = f"{landmark_type}_{x}_{y}_{z}"
        self.landmarks[key] = (x, y, z)
        self.total_landmarks += 1

        log.info("spatial_memory.landmark_discovered",
                 type=landmark_type, pos=f"({x},{y},{z})")

    def observe_wall(self, x: int, y: int, z: int):
        """Record a non-walkable tile."""
        floor = self._get_floor(z)
        cell = floor.get(x, y)
        cell.walkable = False
        cell.cell_type = CellType.WALL.value
        cell.explored = True
        floor.set(x, y, cell)

    def observe_loot(self, x: int, y: int, z: int, value: float):
        """Record loot value at a position."""
        floor = self._get_floor(z)
        cell = floor.get(x, y)
        cell.loot_value += value
        floor.set(x, y, cell)

    def observe_damage(self, x: int, y: int, z: int, amount: float):
        """Record damage taken at a position."""
        floor = self._get_floor(z)
        cell = floor.get(x, y)
        cell.damage_taken += amount
        floor.set(x, y, cell)

    # ═══════════════════════════════════════════════════════
    #  QUERY — What does NEXUS know about the world?
    # ═══════════════════════════════════════════════════════

    def is_explored(self, x: int, y: int, z: int) -> bool:
        """Has this cell been seen before?"""
        if z not in self.floors:
            return False
        return self.floors[z].get(x, y).explored

    def is_walkable(self, x: int, y: int, z: int) -> bool:
        """Is this cell known to be walkable?"""
        if z not in self.floors:
            return False  # Unknown = not walkable
        cell = self.floors[z].get(x, y)
        return cell.walkable

    def get_danger(self, x: int, y: int, z: int) -> float:
        """Get danger score for a position (0-1)."""
        if z not in self.floors:
            return 0.5  # Unknown = moderate danger (assume some risk)
        return self.floors[z].get(x, y).danger_score

    def get_area_danger(self, x: int, y: int, z: int, radius: int = 5) -> float:
        """Average danger in an area."""
        if z not in self.floors:
            return 0.5
        floor = self.floors[z]
        scores = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = floor.get(x + dx, y + dy)
                if cell.explored:
                    scores.append(cell.danger_score)
        return sum(scores) / max(1, len(scores))

    def get_area_value(self, x: int, y: int, z: int, radius: int = 5) -> float:
        """Average loot/XP value in an area."""
        if z not in self.floors:
            return 0
        floor = self.floors[z]
        scores = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = floor.get(x + dx, y + dy)
                if cell.explored:
                    scores.append(cell.value_score)
        return sum(scores) / max(1, len(scores))

    def get_creatures_in_area(self, x: int, y: int, z: int,
                               radius: int = 10) -> dict[str, int]:
        """Get creature distribution around a position."""
        if z not in self.floors:
            return {}
        floor = self.floors[z]
        creatures: dict[str, int] = {}
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                cell = floor.get(x + dx, y + dy)
                for name, count in cell.creature_types.items():
                    creatures[name] = creatures.get(name, 0) + count
        return dict(sorted(creatures.items(), key=lambda x: x[1], reverse=True))

    def find_nearest_landmark(self, x: int, y: int, z: int,
                               landmark_type: str = "") -> Optional[tuple[int, int, int, float]]:
        """Find nearest landmark of a given type. Returns (x, y, z, distance)."""
        best = None
        best_dist = float("inf")

        for key, (lx, ly, lz) in self.landmarks.items():
            if landmark_type and not key.startswith(landmark_type):
                continue
            if lz != z:
                continue  # Same floor only for distance
            dist = math.sqrt((lx - x) ** 2 + (ly - y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = (lx, ly, lz, dist)

        return best

    # ═══════════════════════════════════════════════════════
    #  FRONTIERS — Where should NEXUS explore next?
    # ═══════════════════════════════════════════════════════

    def compute_frontiers(self, current_z: int = 7, max_frontiers: int = 20) -> list[dict]:
        """
        Find exploration frontiers — the boundary between known and unknown.

        A frontier is a walkable explored cell adjacent to at least one
        unexplored cell. These are the optimal exploration targets.

        Returns list of frontier points sorted by exploration priority:
        - Prefer frontiers near landmarks (stairs, etc.)
        - Prefer frontiers in low-danger areas
        - Prefer frontiers near high-value areas
        """
        if current_z not in self.floors:
            return []

        floor = self.floors[current_z]
        frontiers = []

        for (x, y), cell in floor.cells.items():
            if not cell.walkable:
                continue

            # Check if any adjacent cell is unexplored
            has_unknown_neighbor = False
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                nx, ny = x + dx, y + dy
                neighbor = floor.get(nx, ny)
                if not neighbor.explored:
                    has_unknown_neighbor = True
                    break

            if has_unknown_neighbor:
                # Score this frontier
                danger = cell.danger_score
                value = cell.value_score
                recency = time.time() - cell.last_seen if cell.last_seen > 0 else 99999

                # Priority: high value + low danger + not recently seen
                priority = (value * 0.4) + ((1 - danger) * 0.3) + min(1.0, recency / 3600) * 0.3

                frontiers.append({
                    "x": x, "y": y, "z": current_z,
                    "priority": round(priority, 3),
                    "danger": round(danger, 3),
                    "value": round(value, 3),
                    "nearby_creatures": self.get_creatures_in_area(x, y, current_z, radius=3),
                })

        # Sort by priority descending, take top N
        frontiers.sort(key=lambda f: f["priority"], reverse=True)
        self.frontiers = [(f["x"], f["y"], f["z"]) for f in frontiers[:max_frontiers]]

        return frontiers[:max_frontiers]

    # ═══════════════════════════════════════════════════════
    #  ZONE DISCOVERY — Auto-detect meaningful areas
    # ═══════════════════════════════════════════════════════

    def discover_zones(self, z: int = 7) -> list[Zone]:
        """
        Cluster explored cells into meaningful zones.
        Uses creature distribution as the primary clustering signal.
        """
        if z not in self.floors:
            return []

        floor = self.floors[z]

        # Simple grid-based clustering: divide map into 20x20 chunks
        chunk_size = 20
        chunks: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

        for (x, y), cell in floor.cells.items():
            if cell.explored and cell.walkable:
                chunk_key = (x // chunk_size, y // chunk_size)
                chunks[chunk_key].append((x, y))

        zones = []
        for chunk_key, positions in chunks.items():
            if len(positions) < 5:
                continue  # Too small to be a zone

            # Calculate zone center and properties
            cx = sum(p[0] for p in positions) // len(positions)
            cy = sum(p[1] for p in positions) // len(positions)

            # Aggregate creature data
            creatures: dict[str, int] = {}
            total_danger = 0
            total_value = 0
            total_deaths = 0
            for x, y in positions:
                cell = floor.get(x, y)
                total_danger += cell.danger_score
                total_value += cell.value_score
                total_deaths += cell.death_count
                for name, count in cell.creature_types.items():
                    creatures[name] = creatures.get(name, 0) + count

            avg_danger = total_danger / len(positions)
            avg_value = total_value / len(positions)

            # Auto-name based on dominant creature
            if creatures:
                dominant = max(creatures, key=creatures.get)
                name = f"{dominant} Area ({cx},{cy},z{z})"
            else:
                name = f"Area ({cx},{cy},z{z})"

            zone = Zone(
                name=name,
                center_x=cx, center_y=cy, z=z,
                radius=chunk_size // 2,
                avg_danger=round(avg_danger, 3),
                avg_value=round(avg_value, 3),
                creature_distribution=creatures,
                total_deaths=total_deaths,
                total_visits=len(positions),
            )
            zones.append(zone)

        self.zones = zones
        return zones

    # ═══════════════════════════════════════════════════════
    #  CONTEXT FOR AI REASONING
    # ═══════════════════════════════════════════════════════

    def get_exploration_context(self, x: int, y: int, z: int,
                                 radius: int = 15) -> dict:
        """
        Build a compact context block for the strategic brain.
        Describes what NEXUS knows about the surrounding area.
        """
        area_danger = self.get_area_danger(x, y, z, radius)
        area_value = self.get_area_value(x, y, z, radius)
        creatures = self.get_creatures_in_area(x, y, z, radius)
        frontiers = self.compute_frontiers(z, max_frontiers=5)
        nearest_depot = self.find_nearest_landmark(x, y, z, "depot")
        nearest_stair_down = self.find_nearest_landmark(x, y, z, "stair_down")
        nearest_stair_up = self.find_nearest_landmark(x, y, z, "stair_up")

        # Count explored vs total in radius
        explored = 0
        total = 0
        if z in self.floors:
            floor = self.floors[z]
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    total += 1
                    if floor.get(x + dx, y + dy).explored:
                        explored += 1

        return {
            "position": {"x": x, "y": y, "z": z},
            "exploration": {
                "explored_ratio": round(explored / max(1, total), 2),
                "total_cells_explored": self.total_cells_explored,
                "floors_known": list(self.floors.keys()),
                "landmarks_discovered": self.total_landmarks,
            },
            "area_assessment": {
                "danger": round(area_danger, 2),
                "value": round(area_value, 2),
                "creatures": dict(list(creatures.items())[:5]),
            },
            "frontiers": frontiers[:3],
            "nearest_landmarks": {
                "depot": f"({nearest_depot[0]},{nearest_depot[1]})" if nearest_depot else "unknown",
                "stair_down": f"({nearest_stair_down[0]},{nearest_stair_down[1]})" if nearest_stair_down else "unknown",
                "stair_up": f"({nearest_stair_up[0]},{nearest_stair_up[1]})" if nearest_stair_up else "unknown",
            },
        }

    # ═══════════════════════════════════════════════════════
    #  PATHFINDING — A* on known map
    # ═══════════════════════════════════════════════════════

    def find_path(self, start_x: int, start_y: int,
                   end_x: int, end_y: int, z: int,
                   avoid_danger: bool = True,
                   max_steps: int = 200) -> list[tuple[int, int]]:
        """
        A* pathfinding on explored, walkable cells.

        Cost function considers:
        - Distance (primary)
        - Danger level (avoids death spots)
        - Creature density (avoids pulling)
        """
        import heapq

        if z not in self.floors:
            return []

        floor = self.floors[z]
        start = (start_x, start_y)
        end = (end_x, end_y)

        # A* with danger-aware cost
        open_set = [(0, start)]
        came_from: dict[tuple, tuple] = {}
        g_score = {start: 0}
        visited = set()

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            if current in visited:
                continue
            visited.add(current)

            if len(visited) > max_steps:
                break  # Too far — give up

            # Explore neighbors (8 directions)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                cell = floor.get(nx, ny)
                if not cell.walkable:
                    continue

                # Movement cost: 1 for cardinal, 1.414 for diagonal
                move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0

                # Danger penalty
                if avoid_danger and cell.danger_score > 0.3:
                    move_cost += cell.danger_score * 5

                tentative_g = g_score[current] + move_cost

                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    # Heuristic: euclidean distance to goal
                    h = math.sqrt((nx - end_x) ** 2 + (ny - end_y) ** 2)
                    f = tentative_g + h
                    heapq.heappush(open_set, (f, neighbor))

        return []  # No path found

    # ═══════════════════════════════════════════════════════
    #  INTERNAL
    # ═══════════════════════════════════════════════════════

    def _get_floor(self, z: int) -> Floor:
        if z not in self.floors:
            self.floors[z] = Floor(z)
        return self.floors[z]

    def _serialize(self) -> dict:
        """Serialize to JSON-friendly dict."""
        data = {
            "version": 2,
            "total_explored": self.total_cells_explored,
            "landmarks": self.landmarks,
            "floors": {},
        }

        for z, floor in self.floors.items():
            floor_data = {}
            for (x, y), cell in floor.cells.items():
                if cell.explored:  # Only persist explored cells
                    floor_data[f"{x},{y}"] = {
                        "t": cell.cell_type,
                        "w": cell.walkable,
                        "v": cell.visit_count,
                        "d": cell.death_count,
                        "c": cell.creatures_seen,
                        "l": round(cell.loot_value, 1),
                        "p": cell.player_sightings,
                        "lm": cell.landmark,
                        "ct": cell.creature_types,
                    }
            data["floors"][str(z)] = floor_data

        # Zones
        data["zones"] = [asdict(z) for z in self.zones]

        return data

    def _deserialize(self, data: dict):
        """Deserialize from JSON."""
        self.total_cells_explored = data.get("total_explored", 0)
        self.landmarks = data.get("landmarks", {})

        for z_str, floor_data in data.get("floors", {}).items():
            z = int(z_str)
            floor = self._get_floor(z)
            for pos_str, cell_data in floor_data.items():
                x, y = pos_str.split(",")
                x, y = int(x), int(y)
                cell = MapCell(
                    cell_type=cell_data.get("t", 0),
                    walkable=cell_data.get("w", False),
                    explored=True,
                    visit_count=cell_data.get("v", 0),
                    death_count=cell_data.get("d", 0),
                    creatures_seen=cell_data.get("c", 0),
                    loot_value=cell_data.get("l", 0),
                    player_sightings=cell_data.get("p", 0),
                    landmark=cell_data.get("lm", ""),
                    creature_types=cell_data.get("ct", {}),
                )
                floor.set(x, y, cell)

        for z_data in data.get("zones", []):
            try:
                self.zones.append(Zone(**z_data))
            except Exception:
                pass

    @property
    def stats(self) -> dict:
        return {
            "total_explored": self.total_cells_explored,
            "floors": len(self.floors),
            "landmarks": self.total_landmarks,
            "zones": len(self.zones),
            "frontiers": len(self.frontiers),
        }
