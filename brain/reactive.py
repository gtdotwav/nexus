"""
NEXUS Agent — Reactive Brain v2

Lightning-fast decision engine for survival and combat execution.
Runs at 40 ticks/second (<25ms per tick).

This is the "instinct" layer — it keeps the character alive
while the strategic brain handles the thinking.

v2 Improvements:
- Consciousness integration — emotional modifiers affect thresholds dynamically
- Combo/chain attack system — maximizes DPS with optimal spell sequencing
- Spell rotation override — strategic brain can dictate spell order
- Event reporting — feeds kills, heals, close calls back to consciousness
- Repositioning system — executes movement commands from strategic brain
"""

from __future__ import annotations

import asyncio
import time
import random
import structlog
from typing import Optional
from collections import deque

from core.state import GameState, AgentMode, ThreatLevel

log = structlog.get_logger()


class HumanizedInput:
    """
    Simulates human-like keyboard and mouse input.
    All timing is randomized to avoid detection.

    v3 optimization: Controllers are singletons created once at init.
    Previous version created new Controller() per call = 3-5ms overhead.
    Now: 0ms overhead (reuse existing instance).
    """

    def __init__(self, config: dict):
        self.config = config["humanization"]
        self.enabled = self.config["enabled"]
        self._last_action_time = 0.0

        # ─── SINGLETON CONTROLLERS (created once, reused forever) ───
        # This is THE critical fix: pynput.Controller() allocates X11/Quartz
        # resources each time. Creating it once saves 3-5ms per input action.
        self._keyboard = None
        self._mouse = None
        self._key_map = {}
        self._pynput_available = False

        try:
            from pynput.keyboard import Controller as KBController, Key
            from pynput.mouse import Controller as MouseController, Button

            self._keyboard = KBController()
            self._mouse = MouseController()
            self._Button = Button
            self._pynput_available = True

            # Pre-build key map (avoid dict creation per call)
            self._key_map = {
                "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
                "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
                "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
                "space": Key.space, "enter": Key.enter, "escape": Key.esc,
                "ctrl": Key.ctrl_l, "shift": Key.shift_l, "alt": Key.alt_l,
                "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
            }

            log.info("input.controllers_initialized", keyboard=True, mouse=True)

        except ImportError:
            log.warning("input.pynput_unavailable",
                        reason="pynput not installed, input disabled")

    async def press_key(self, key: str, hold_range: tuple = None):
        """Press a keyboard key with human-like timing."""
        if not self._pynput_available:
            return

        if self.enabled:
            delay_min, delay_max = self.config["inter_action_delay"]
            await asyncio.sleep(random.uniform(delay_min, delay_max))

        actual_key = self._key_map.get(key.lower(), key)

        # Humanized hold time
        if hold_range is None:
            hold_min, hold_max = self.config["key_hold_range"]
        else:
            hold_min, hold_max = hold_range

        hold_time = random.uniform(hold_min, hold_max)

        self._keyboard.press(actual_key)
        await asyncio.sleep(hold_time)
        self._keyboard.release(actual_key)

        self._last_action_time = time.time()

    async def click(self, x: int, y: int, button: str = "left"):
        """Click at coordinates with human-like mouse movement."""
        if not self._pynput_available:
            return

        if self.enabled:
            delay_min, delay_max = self.config["inter_action_delay"]
            await asyncio.sleep(random.uniform(delay_min, delay_max))

        # Add gaussian noise to coordinates
        noise_std = self.config["coordinate_noise_std"]
        target_x = int(x + random.gauss(0, noise_std))
        target_y = int(y + random.gauss(0, noise_std))

        # Move mouse (TODO: implement Bézier curve movement)
        self._mouse.position = (target_x, target_y)

        # Click with human-like hold
        hold_min, hold_max = self.config["click_hold_range"]
        hold_time = random.uniform(hold_min, hold_max)

        btn = self._Button.left if button == "left" else self._Button.right
        self._mouse.press(btn)
        await asyncio.sleep(hold_time)
        self._mouse.release(btn)

        self._last_action_time = time.time()

    async def type_text(self, text: str):
        """Type text with human-like keystroke timing."""
        if not self._pynput_available:
            return

        for char in text:
            delay = random.uniform(0.05, 0.15)  # Typing speed variation
            await asyncio.sleep(delay)
            self._keyboard.press(char)
            await asyncio.sleep(random.uniform(0.03, 0.08))
            self._keyboard.release(char)


class ReactiveBrain:
    """
    Fast decision engine for survival and combat execution.

    Priority system (lower number = higher priority):
        0: Emergency heal (HP critical) — potion + spell combo
        1: Anti-PK flee (hostile player)
        2: Normal heal (HP below threshold)
        3: Mana restore
        4: Attack — combo chain system
        5: Loot corpse
        6: Use food
        7: Navigate / reposition

    v2 Features:
        - Consciousness-driven dynamic thresholds
        - Spell combo chains for maximum DPS
        - Strategic brain spell rotation overrides
        - Event reporting to consciousness
        - Repositioning commands from strategic brain
    """

    def __init__(self, state: GameState, reactive_config: dict, input_config: dict):
        self.state = state
        self.config = reactive_config
        self.input = HumanizedInput(input_config)

        # Reference to consciousness (set by agent after init)
        self.consciousness = None

        # Healing thresholds (base values — dynamically adjusted by consciousness)
        self._base_critical_hp = reactive_config["healing"]["critical_hp_percent"]
        self._base_medium_hp = reactive_config["healing"]["medium_hp_percent"]
        self._base_mana_threshold = reactive_config["healing"]["mana_restore_percent"]
        self.critical_hp = self._base_critical_hp
        self.medium_hp = self._base_medium_hp
        self.mana_threshold = self._base_mana_threshold

        # Spell and potion configs
        self.heal_spells = reactive_config["healing"]["spells"]
        self.potions = reactive_config["healing"]["potions"]

        # Anti-PK config
        self.anti_pk = reactive_config["anti_pk"]

        # ─── Combo/Chain Attack System ─────────────────────
        # Default offensive spell rotation (can be overridden by strategic brain)
        self._spell_rotation: list[str] = ["exori gran", "exori", "exori min"]
        self._rotation_index: int = 0
        self._combo_active: bool = False
        self._combo_chain: deque[str] = deque(maxlen=5)  # Last 5 spells for chain tracking

        # ─── Aggression Settings ──────────────────────────
        self.chase_distance: int = 3  # Max SQMs to chase a target
        self.attack_mode: str = "balanced"  # full_attack | balanced | defensive
        self.pull_count: int = 2  # Target monsters to pull per engagement

        # ─── Repositioning ────────────────────────────────
        self._reposition_target: Optional[str] = None  # Direction to reposition
        self._reposition_until: float = 0.0  # Timestamp when reposition ends

        # ─── Cooldown Tracking ────────────────────────────
        self._last_heal_time = 0.0
        self._last_potion_time = 0.0
        self._last_attack_time = 0.0
        self._global_cooldown = 0.0

        # ─── Performance Tracking ─────────────────────────
        self._ticks = 0
        self._actions_taken = 0
        self._heals_cast = 0
        self._emergency_heals = 0
        self._last_modifier_update = 0.0

        # Hotkey mappings — loaded from config, with sensible defaults
        default_hotkeys = {
            "exura": "f1",
            "exura gran": "f2",
            "exura vita": "f3",
            "exori": "f4",
            "exori gran": "f5",
            "exori min": "f6",
            "great_health_potion": "f7",
            "great_mana_potion": "f8",
            "exeta res": "f9",
            "utani hur": "f10",
        }
        config_hotkeys = reactive_config.get("hotkeys", {})
        self.hotkeys = {**default_hotkeys, **config_hotkeys}

    async def tick(self):
        """
        Single tick of the reactive brain.
        Evaluates conditions and executes the highest priority action.
        """
        now = time.time()
        self._ticks += 1

        # Global cooldown check (prevent action spam)
        if now < self._global_cooldown:
            return

        # Apply consciousness modifiers every 5 seconds
        if now - self._last_modifier_update > 5.0:
            self._apply_consciousness_modifiers()
            self._last_modifier_update = now

        # Priority 0: Emergency heal — use EVERYTHING available
        if self.state.hp_percent <= self.critical_hp:
            await self._emergency_heal()
            return

        # Priority 1: Anti-PK
        if self.anti_pk["enabled"] and self.state.threat_level >= ThreatLevel.HIGH:
            await self._anti_pk_react()
            return

        # Priority 2: Normal healing
        if self.state.hp_percent <= self.medium_hp:
            await self._normal_heal()
            return

        # Priority 3: Mana restore
        if self.state.mana_percent <= self.mana_threshold:
            await self._restore_mana()
            return

        # Priority 4: Repositioning (if strategic brain requested it)
        if self._reposition_target and now < self._reposition_until:
            await self._execute_reposition()
            return

        # Priority 5: Attack (if in hunting mode)
        if self.state.mode == AgentMode.HUNTING and self.state.current_target:
            await self._attack_combo()
            return

        # Priority 6-7 handled by skill engine (loot, food, navigation)

    # ─── Emergency Heal ───────────────────────────────────

    async def _emergency_heal(self):
        """
        CRITICAL: Character about to die.
        Use BOTH potion AND spell simultaneously for maximum healing.
        This is a super-player technique — stacking heal sources in the same tick.
        """
        self._emergency_heals += 1
        heal_start = time.perf_counter()

        log.warning(
            "reactive.emergency_heal",
            hp=round(self.state.hp_percent, 1),
            mana=round(self.state.mana_percent, 1),
        )

        # Step 1: Health potion FIRST (instant, no mana cost)
        potion_used = False
        for potion in self.potions:
            if "health" in potion["type"]:
                await self._use_potion(potion["type"])
                potion_used = True
                break

        # Step 2: Strongest heal spell ON TOP of potion (combo heal)
        # Sort by mana_cost descending — highest cost = strongest heal
        for spell in sorted(self.heal_spells, key=lambda s: s["mana_cost"], reverse=True):
            if (self.state.mana_percent * self.state.mana_max / 100 >= spell["mana_cost"]
                    and self.state.is_spell_ready(spell["name"])):
                await self._cast_spell(spell["name"])
                break

        # Report to consciousness
        reaction_ms = (time.perf_counter() - heal_start) * 1000
        if self.consciousness:
            self.consciousness.on_heal_success("emergency", reaction_ms)

    # ─── Anti-PK ──────────────────────────────────────────

    async def _anti_pk_react(self):
        """
        Hostile player detected. Execute escape protocol.
        1. Cast haste spell
        2. Move toward nearest safe zone
        3. Report to consciousness for threat profiling
        """
        players = [p.name for p in self.state.nearby_players if p.skull or p.is_attacking]

        log.warning(
            "reactive.anti_pk",
            threat=self.state.threat_level.name,
            players=players,
        )

        self.state.set_mode(AgentMode.FLEEING)

        # Cast haste if available
        if self.state.is_spell_ready("utani hur"):
            await self._cast_spell("utani hur")

        # Report each hostile player to consciousness
        if self.consciousness:
            for name in players:
                self.consciousness._update_threat_profile(name, {
                    "threat": "hostile",
                    "last_attacked": time.time(),
                })

        # TODO: Navigate to nearest depot/safe zone via skill escape waypoints

    # ─── Normal Healing ───────────────────────────────────

    async def _normal_heal(self):
        """
        HP below comfort threshold.
        Use appropriate heal based on current HP level.
        """
        now = time.time()
        if now - self._last_heal_time < 0.8:  # Global heal cooldown
            return

        heal_start = time.perf_counter()

        for spell in self.heal_spells:
            if (self.state.hp_percent <= spell["hp_threshold"]
                    and self.state.mana_percent * self.state.mana_max / 100 >= spell["mana_cost"]
                    and self.state.is_spell_ready(spell["name"])):
                await self._cast_spell(spell["name"])
                self._last_heal_time = now
                self._heals_cast += 1

                # Report to consciousness
                reaction_ms = (time.perf_counter() - heal_start) * 1000
                if self.consciousness:
                    self.consciousness.on_heal_success(spell["name"], reaction_ms)
                return

    # ─── Mana Restore ─────────────────────────────────────

    async def _restore_mana(self):
        """Use mana potion when mana is low."""
        now = time.time()
        if now - self._last_potion_time < 0.8:  # Potion cooldown
            return

        for potion in self.potions:
            if "mana" in potion["type"]:
                await self._use_potion(potion["type"])
                self._last_potion_time = now
                return

    # ─── Combo Attack System ──────────────────────────────

    async def _attack_combo(self):
        """
        Execute attack using the spell rotation system.

        Super-player technique: cycle through spells in optimal order
        to maximize DPS while respecting cooldowns. The strategic brain
        can override the rotation for specific situations.
        """
        now = time.time()
        if now - self._last_attack_time < 0.8:  # Minimum attack interval
            return

        # Try spells in rotation order
        rotation = self._spell_rotation
        attempts = len(rotation)

        for _ in range(attempts):
            spell_name = rotation[self._rotation_index % len(rotation)]

            if self.state.is_spell_ready(spell_name):
                await self._cast_spell(spell_name)
                self._last_attack_time = now
                self._combo_chain.append(spell_name)
                self._rotation_index += 1
                self._actions_taken += 1
                return

            # Spell on cooldown — try next in rotation
            self._rotation_index += 1

        # All spells on cooldown — try basic attack as fallback
        if self.state.is_spell_ready("exori min"):
            await self._cast_spell("exori min")
            self._last_attack_time = now

    # ─── Repositioning ────────────────────────────────────

    async def _execute_reposition(self):
        """
        Execute a repositioning command from the strategic brain.
        Maps direction strings to keyboard arrow keys.
        Diagonal movements press two keys simultaneously.
        """
        # Cardinal → single key, Diagonal → two keys pressed together
        direction_map = {
            "n": ["up"], "s": ["down"], "e": ["right"], "w": ["left"],
            "ne": ["up", "right"], "nw": ["up", "left"],
            "se": ["down", "right"], "sw": ["down", "left"],
        }

        keys = direction_map.get(self._reposition_target, [])
        if keys:
            if len(keys) == 1:
                await self.input.press_key(keys[0])
            else:
                # Diagonal: press both keys simultaneously using pynput
                await self._press_diagonal(keys[0], keys[1])
            log.debug("reactive.repositioned", direction=self._reposition_target, keys=keys)

        # Clear reposition after executing
        self._reposition_target = None

    async def _press_diagonal(self, key1: str, key2: str):
        """Press two keys simultaneously for diagonal movement.
        Uses the singleton keyboard controller from HumanizedInput."""
        if not self.input._pynput_available:
            return

        k1 = self.input._key_map.get(key1)
        k2 = self.input._key_map.get(key2)
        if k1 and k2:
            hold_min, hold_max = self.input.config["key_hold_range"]
            hold_time = random.uniform(hold_min, hold_max)

            self.input._keyboard.press(k1)
            self.input._keyboard.press(k2)
            await asyncio.sleep(hold_time)
            self.input._keyboard.release(k2)
            self.input._keyboard.release(k1)

    # ─── Spell & Potion Execution ─────────────────────────

    async def _cast_spell(self, spell_name: str):
        """Cast a spell using its mapped hotkey."""
        hotkey = self.hotkeys.get(spell_name)
        if hotkey:
            await self.input.press_key(hotkey)
            # Set cooldown
            self.state.set_cooldown(spell_name, 1000)  # Default 1s cooldown
            self._global_cooldown = time.time() + 0.15  # 150ms global CD
            log.debug("reactive.cast", spell=spell_name, hotkey=hotkey)
        else:
            log.warning("reactive.no_hotkey", spell=spell_name)

    async def _use_potion(self, potion_type: str):
        """Use a potion via its mapped hotkey."""
        hotkey = self.hotkeys.get(potion_type)
        if hotkey:
            await self.input.press_key(hotkey)
            self._global_cooldown = time.time() + 0.15
            log.debug("reactive.potion", type=potion_type, hotkey=hotkey)

    # ─── Consciousness Integration ────────────────────────

    def _apply_consciousness_modifiers(self):
        """
        Apply emotional modifiers from consciousness to adjust thresholds.
        High confidence → tighter healing (react later, more aggressive).
        Low confidence → wider margins (react earlier, more cautious).
        """
        if not self.consciousness:
            return

        modifiers = self.consciousness.get_decision_modifiers()

        # Adjust healing thresholds
        self.critical_hp = max(20, min(50,
            self._base_critical_hp + modifiers.get("heal_critical_modifier", 0)
        ))
        self.medium_hp = max(40, min(80,
            self._base_medium_hp + modifiers.get("heal_medium_modifier", 0)
        ))

        # Adjust combat aggression
        aggression = modifiers.get("aggression_level", 0.5)
        if aggression > 0.7:
            self.chase_distance = min(8, self.chase_distance + 1)
        elif aggression < 0.3:
            self.chase_distance = max(1, self.chase_distance - 1)

    # ─── External Control Methods ─────────────────────────

    def update_healing_thresholds(self, adjustments: dict):
        """
        Called by strategic brain to dynamically adjust healing.
        Example: In a dangerous area, increase critical threshold from 30 to 40.
        """
        if "critical_hp" in adjustments:
            old = self._base_critical_hp
            self._base_critical_hp = adjustments["critical_hp"]
            self.critical_hp = self._base_critical_hp
            log.info("reactive.threshold_adjusted", param="critical_hp", old=old, new=self.critical_hp)

        if "medium_hp" in adjustments:
            old = self._base_medium_hp
            self._base_medium_hp = adjustments["medium_hp"]
            self.medium_hp = self._base_medium_hp
            log.info("reactive.threshold_adjusted", param="medium_hp", old=old, new=self.medium_hp)

        if "mana_threshold" in adjustments:
            old = self._base_mana_threshold
            self._base_mana_threshold = adjustments["mana_threshold"]
            self.mana_threshold = self._base_mana_threshold
            log.info("reactive.threshold_adjusted", param="mana_threshold", old=old, new=self.mana_threshold)

    def update_aggression(self, settings: dict):
        """
        Called by strategic brain to adjust aggression parameters.
        """
        if "chase_distance" in settings:
            self.chase_distance = max(1, min(8, settings["chase_distance"]))
            log.info("reactive.chase_distance", value=self.chase_distance)

        if "attack_mode" in settings:
            self.attack_mode = settings["attack_mode"]
            log.info("reactive.attack_mode", mode=self.attack_mode)

        if "pull_count" in settings:
            self.pull_count = max(1, min(5, settings["pull_count"]))
            log.info("reactive.pull_count", count=self.pull_count)

    def set_spell_rotation(self, rotation: list[str]):
        """
        Override the spell rotation. Called by strategic brain when
        a specific combo is needed for current situation.
        """
        if rotation:
            self._spell_rotation = rotation
            self._rotation_index = 0
            log.info("reactive.rotation_set", rotation=rotation)

    def set_reposition_target(self, direction: str):
        """
        Set a repositioning target. The brain moves 1 SQM in the given direction
        on the next available tick.
        """
        self._reposition_target = direction
        self._reposition_until = time.time() + 2.0  # 2 second window to execute

    # ─── Stats ────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        return {
            "ticks": self._ticks,
            "actions": self._actions_taken,
            "heals": self._heals_cast,
            "emergency_heals": self._emergency_heals,
            "current_rotation": self._spell_rotation,
            "critical_hp": self.critical_hp,
            "medium_hp": self.medium_hp,
            "chase_distance": self.chase_distance,
            "attack_mode": self.attack_mode,
        }
