"""
NEXUS Agent — Behavior Engine

Executes skill-defined special behaviors:
- Auto-eat food for HP regen
- Pull monsters with challenge (exeta res)
- Smart positioning (diagonal against fire-wave creatures)
- Buff management (utani hur, utamo vita, etc.)
- Stamina monitoring

Each behavior runs independently with its own timer/cooldown.
Behaviors are loaded dynamically from the active skill's YAML config.
"""

from __future__ import annotations

import asyncio
import time
import math
import random
import structlog
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState

log = structlog.get_logger()


@dataclass
class BehaviorConfig:
    """Configuration for a single behavior."""
    name: str
    enabled: bool = True
    interval_seconds: float = 0
    last_executed: float = 0
    params: dict = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        if not self.enabled:
            return False
        if self.interval_seconds <= 0:
            return True
        return (time.time() - self.last_executed) >= self.interval_seconds


class BehaviorEngine:
    """
    Manages and executes special behaviors defined in skill config.

    Behaviors are independent mini-systems, each with their own
    trigger conditions, cooldowns, and execution logic.
    They run at lower priority than healing and combat.
    """

    def __init__(self, state: "GameState", input_handler, config: dict):
        self.state = state
        self.input = input_handler
        self.config = config

        # Registered behaviors
        self.behaviors: dict[str, BehaviorConfig] = {}

        # Hotkey references
        self.hotkeys: dict[str, str] = {}

    def load_behaviors(self, behavior_config: dict, hotkeys: dict = None):
        """Load behavior configurations from active skill."""
        self.hotkeys = hotkeys or {}

        # Auto-eat food
        if "auto_eat" in behavior_config:
            eat = behavior_config["auto_eat"]
            self.behaviors["auto_eat"] = BehaviorConfig(
                name="auto_eat",
                enabled=eat.get("enabled", True),
                interval_seconds=eat.get("interval_seconds", 120),
                params={"item": eat.get("item", "meat")},
            )

        # Pull monsters
        if "pull_monsters" in behavior_config:
            pull = behavior_config["pull_monsters"]
            self.behaviors["pull_monsters"] = BehaviorConfig(
                name="pull_monsters",
                enabled=pull.get("enabled", True),
                interval_seconds=3.0,  # Check every 3s
                params={
                    "spell": pull.get("spell", "exeta res"),
                    "when": pull.get("when", "monster_count_below_2"),
                },
            )

        # Smart positioning
        if "smart_positioning" in behavior_config:
            pos = behavior_config["smart_positioning"]
            self.behaviors["smart_positioning"] = BehaviorConfig(
                name="smart_positioning",
                enabled=pos.get("enabled", True),
                interval_seconds=1.0,  # Check every second
                params={
                    "prefer_diagonal": pos.get("prefer_diagonal", True),
                    "avoid_straight_line": pos.get("avoid_straight_line", []),
                },
            )

        # Stamina check
        if "stamina_check" in behavior_config:
            stam = behavior_config["stamina_check"]
            self.behaviors["stamina_check"] = BehaviorConfig(
                name="stamina_check",
                enabled=stam.get("enabled", True),
                interval_seconds=300,  # Check every 5min
                params={
                    "logout_below": stam.get("logout_below", 14),
                    "warning_below": stam.get("warning_below", 20),
                },
            )

        # Buff management (if skill defines buffs)
        if "buffs" in behavior_config:
            for buff in behavior_config["buffs"]:
                name = f"buff_{buff['spell']}"
                self.behaviors[name] = BehaviorConfig(
                    name=name,
                    enabled=buff.get("enabled", True),
                    interval_seconds=buff.get("duration_seconds", 120) - 5,
                    params={"spell": buff["spell"]},
                )

        log.info("behaviors.loaded", count=len(self.behaviors),
                 active=[b.name for b in self.behaviors.values() if b.enabled])

    async def tick(self) -> list[str]:
        """
        Execute all ready behaviors. Returns list of actions taken.

        Called by agent at lower priority than combat.
        """
        actions = []

        for name, behavior in self.behaviors.items():
            if not behavior.ready:
                continue

            try:
                action = await self._execute(behavior)
                if action:
                    behavior.last_executed = time.time()
                    actions.append(action)
            except Exception as e:
                log.error("behavior.error", name=name, error=str(e))

        return actions

    async def _execute(self, behavior: BehaviorConfig) -> Optional[str]:
        """Execute a single behavior. Returns action description or None."""

        if behavior.name == "auto_eat":
            return await self._auto_eat(behavior)

        elif behavior.name == "pull_monsters":
            return await self._pull_monsters(behavior)

        elif behavior.name == "smart_positioning":
            return await self._smart_positioning(behavior)

        elif behavior.name == "stamina_check":
            return self._stamina_check(behavior)

        elif behavior.name.startswith("buff_"):
            return await self._cast_buff(behavior)

        return None

    async def _auto_eat(self, behavior: BehaviorConfig) -> Optional[str]:
        """Use food item for HP regeneration."""
        food_item = behavior.params.get("item", "meat")
        food_hotkey = self.hotkeys.get(food_item)

        if food_hotkey:
            await self.input.press_key(food_hotkey)
            log.debug("behavior.ate_food", item=food_item)
            return f"ate_{food_item}"

        # Alternative: right-click food in inventory (needs screen position)
        # For now, food requires a hotkey mapping
        return None

    async def _pull_monsters(self, behavior: BehaviorConfig) -> Optional[str]:
        """Use challenge spell to pull monsters when count is low."""
        spell = behavior.params.get("spell", "exeta res")
        condition = behavior.params.get("when", "monster_count_below_2")

        # Parse condition
        should_pull = False
        if condition.startswith("monster_count_below_"):
            threshold = int(condition.split("_")[-1])
            nearby_monsters = [
                c for c in self.state.battle_list if not c.is_player
            ]
            should_pull = len(nearby_monsters) < threshold

        if should_pull:
            hotkey = self.hotkeys.get(spell)
            if hotkey and self.state.is_spell_ready(spell):
                await self.input.press_key(hotkey)
                log.debug("behavior.pulled", spell=spell)
                return f"pull_{spell}"

        return None

    async def _smart_positioning(self, behavior: BehaviorConfig) -> Optional[str]:
        """
        Adjust position to stay diagonal to dangerous creatures.

        Dragon Lords have a fire wave that hits in a straight line.
        Staying diagonal avoids this attack entirely.
        """
        avoid_creatures = behavior.params.get("avoid_straight_line", [])
        prefer_diagonal = behavior.params.get("prefer_diagonal", True)

        if not prefer_diagonal or not avoid_creatures:
            return None

        pos = self.state.position
        if pos is None:
            return None

        # Check if any dangerous creature is on same axis
        for creature in self.state.battle_list:
            if creature.name not in avoid_creatures:
                continue

            # Check if creature is in a straight line (same x or same y)
            # This would need creature position, which we track if available
            cx = getattr(creature, "x", None)
            cy = getattr(creature, "y", None)
            if cx is None or cy is None:
                continue

            same_x = cx == pos.x
            same_y = cy == pos.y

            if same_x or same_y:
                # We're in the fire line — need to move diagonally
                # Determine which direction to move
                dx = 1 if cx >= pos.x else -1
                dy = 1 if cy >= pos.y else -1

                # Move perpendicular to create diagonal
                if same_x:
                    # Same column — move left or right
                    direction = "e" if random.random() > 0.5 else "w"
                elif same_y:
                    # Same row — move up or down
                    direction = "n" if random.random() > 0.5 else "s"
                else:
                    continue

                # Use arrow key to reposition
                key_map = {"n": "up", "s": "down", "e": "right", "w": "left"}
                await self.input.press_key(key_map[direction])

                log.debug("behavior.repositioned",
                           creature=creature.name,
                           direction=direction,
                           reason="avoid_straight_line")
                return f"reposition_{direction}"

        return None

    def _stamina_check(self, behavior: BehaviorConfig) -> Optional[str]:
        """Check stamina level and warn/logout if too low."""
        stamina_hours = getattr(self.state, "stamina_hours", 42)
        logout_below = behavior.params.get("logout_below", 14)
        warning_below = behavior.params.get("warning_below", 20)

        if stamina_hours <= logout_below:
            log.warning("behavior.stamina_critical",
                         hours=stamina_hours,
                         action="should_logout")
            return "stamina_critical"
        elif stamina_hours <= warning_below:
            log.info("behavior.stamina_low", hours=stamina_hours)
            return "stamina_warning"

        return None

    async def _cast_buff(self, behavior: BehaviorConfig) -> Optional[str]:
        """Cast a buff spell (haste, utamo, etc.)."""
        spell = behavior.params.get("spell", "")
        hotkey = self.hotkeys.get(spell)

        if hotkey and self.state.is_spell_ready(spell):
            # Check mana
            mana_cost = behavior.params.get("mana_cost", 60)
            current_mana = self.state.mana_percent * self.state.mana_max / 100

            if current_mana >= mana_cost:
                await self.input.press_key(hotkey)
                log.debug("behavior.buff_cast", spell=spell)
                return f"buff_{spell}"

        return None

    @property
    def stats(self) -> dict:
        return {
            "active_behaviors": [
                b.name for b in self.behaviors.values() if b.enabled
            ],
            "behavior_states": {
                name: {
                    "enabled": b.enabled,
                    "last_executed": b.last_executed,
                    "ready": b.ready,
                }
                for name, b in self.behaviors.items()
            },
        }
