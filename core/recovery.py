"""
NEXUS Agent — Death Recovery System

Handles the full death → recovery → return cycle:
1. Detect death (HP = 0, game shows death screen)
2. Wait for respawn timer
3. Click to respawn at temple
4. Re-equip gear from depot
5. Rebuff (haste, etc.)
6. Navigate back to hunting area
7. Resume hunting

Also handles:
- Disconnection recovery (detect client disconnect, reconnect)
- Stuck recovery (force unstuck if agent can't move for N seconds)
- Error recovery (restart subsystems that crash)
"""

from __future__ import annotations

import asyncio
import time
import structlog
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState

log = structlog.get_logger()


class RecoveryPhase(Enum):
    """Phases of death recovery."""
    NONE = auto()
    DEATH_DETECTED = auto()
    WAITING_RESPAWN = auto()
    RESPAWNING = auto()
    AT_TEMPLE = auto()
    WALKING_TO_DEPOT = auto()
    RE_EQUIPPING = auto()
    REBUFFING = auto()
    RETURNING_TO_HUNT = auto()
    RECOVERED = auto()


class DeathRecovery:
    """
    Manages the death → recovery → return pipeline.

    Key design decisions:
    - Recovery is autonomous — no player intervention needed
    - Consciousness is notified at every stage for learning
    - Recovery actions feed into death pattern analysis
    - If multiple deaths in short time, consciousness may suggest area change
    """

    def __init__(self, state: "GameState", input_handler, config: dict):
        self.state = state
        self.input = input_handler
        self.config = config

        # Recovery state
        self.phase: RecoveryPhase = RecoveryPhase.NONE
        self.recovery_active: bool = False
        self._phase_start: float = 0
        self._phase_timeout: float = 60  # Max 60s per phase
        self._death_time: float = 0
        self._death_cause: str = ""

        # Respawn settings
        self._respawn_delay: float = 3.0   # Wait before clicking respawn
        self._rebuff_spells: list[str] = []
        self._equip_hotkeys: list[str] = []

        # Stats
        self.total_recoveries: int = 0
        self.total_recovery_time: float = 0
        self.consecutive_deaths: int = 0
        self._last_recovery_end: float = 0.0

    def load_config(self, recovery_config: dict = None):
        """Load recovery settings."""
        if recovery_config:
            self._respawn_delay = recovery_config.get("respawn_delay", 3.0)
            self._rebuff_spells = recovery_config.get("rebuff_spells", [])
            self._equip_hotkeys = recovery_config.get("equip_hotkeys", [])

    def detect_death(self) -> bool:
        """Check if the character has died."""
        if not self.state.is_alive and not self.recovery_active:
            return True
        return False

    async def start_recovery(self, cause: str = "unknown"):
        """Begin the death recovery sequence."""
        if self.recovery_active:
            return

        self.recovery_active = True
        self.phase = RecoveryPhase.DEATH_DETECTED
        self._phase_start = time.time()
        self._death_time = time.time()
        self._death_cause = cause

        # Track consecutive deaths
        if time.time() - self._last_recovery_end < 120:
            self.consecutive_deaths += 1
        else:
            self.consecutive_deaths = 1

        log.info("recovery.death_detected",
                 cause=cause,
                 consecutive=self.consecutive_deaths)

    async def tick(self) -> Optional[str]:
        """
        Process one recovery tick. Returns current phase action.

        Called by the agent's main loop when recovery_active is True.
        During recovery, normal hunting loops are paused.
        """
        if not self.recovery_active:
            # Check for death
            if self.detect_death():
                await self.start_recovery()
                return "death_detected"
            return None

        # Phase timeout protection
        elapsed = time.time() - self._phase_start
        if elapsed > self._phase_timeout:
            log.warning("recovery.phase_timeout", phase=self.phase.name)
            self._advance_phase()

        # Execute current phase
        return await self._execute_phase()

    async def _execute_phase(self) -> str:
        """Execute the current recovery phase."""

        if self.phase == RecoveryPhase.DEATH_DETECTED:
            # Brief pause to let death animation complete
            await asyncio.sleep(1.0)
            self.phase = RecoveryPhase.WAITING_RESPAWN
            self._phase_start = time.time()
            return "waiting_for_respawn_screen"

        elif self.phase == RecoveryPhase.WAITING_RESPAWN:
            # Wait for respawn dialog
            await asyncio.sleep(self._respawn_delay)
            self.phase = RecoveryPhase.RESPAWNING
            self._phase_start = time.time()
            return "waiting_respawn"

        elif self.phase == RecoveryPhase.RESPAWNING:
            # Click respawn button
            # In Tibia, press Enter or click "OK" to respawn at temple
            await self.input.press_key("enter")
            await asyncio.sleep(2.0)

            # Mark as alive again
            self.state.is_alive = True
            self.phase = RecoveryPhase.AT_TEMPLE
            self._phase_start = time.time()

            log.info("recovery.respawned")
            return "respawned"

        elif self.phase == RecoveryPhase.AT_TEMPLE:
            # At temple — check if we need to re-equip
            if self._equip_hotkeys:
                self.phase = RecoveryPhase.RE_EQUIPPING
            elif self._rebuff_spells:
                self.phase = RecoveryPhase.REBUFFING
            else:
                self.phase = RecoveryPhase.RETURNING_TO_HUNT
            self._phase_start = time.time()
            return "at_temple"

        elif self.phase == RecoveryPhase.RE_EQUIPPING:
            # Re-equip gear from depot
            for hotkey in self._equip_hotkeys:
                await self.input.press_key(hotkey)
                await asyncio.sleep(0.5)

            self.phase = RecoveryPhase.REBUFFING if self._rebuff_spells else RecoveryPhase.RETURNING_TO_HUNT
            self._phase_start = time.time()

            log.info("recovery.re_equipped")
            return "re_equipped"

        elif self.phase == RecoveryPhase.REBUFFING:
            # Cast buff spells (haste, etc.)
            for spell in self._rebuff_spells:
                hotkey = self.config.get("hotkeys", {}).get(spell)
                if hotkey:
                    await self.input.press_key(hotkey)
                    await asyncio.sleep(1.0)

            self.phase = RecoveryPhase.RETURNING_TO_HUNT
            self._phase_start = time.time()

            log.info("recovery.rebuffed", spells=self._rebuff_spells)
            return "rebuffed"

        elif self.phase == RecoveryPhase.RETURNING_TO_HUNT:
            # Signal that we need to navigate back to hunting area
            # The navigator handles the actual pathfinding
            self.phase = RecoveryPhase.RECOVERED
            self._phase_start = time.time()
            return "returning_to_hunt"

        elif self.phase == RecoveryPhase.RECOVERED:
            return await self._complete_recovery()

        return self.phase.name.lower()

    async def _complete_recovery(self) -> str:
        """Finalize recovery and return to normal operations."""
        recovery_time = time.time() - self._death_time

        self.total_recoveries += 1
        self.total_recovery_time += recovery_time
        self._last_recovery_end = time.time()

        self.recovery_active = False
        self.phase = RecoveryPhase.NONE

        log.info("recovery.complete",
                 recovery_time_s=round(recovery_time, 1),
                 cause=self._death_cause,
                 total_recoveries=self.total_recoveries,
                 consecutive=self.consecutive_deaths)

        return "recovery_complete"

    def _advance_phase(self):
        """Force advance to next phase (timeout recovery)."""
        transitions = {
            RecoveryPhase.DEATH_DETECTED: RecoveryPhase.WAITING_RESPAWN,
            RecoveryPhase.WAITING_RESPAWN: RecoveryPhase.RESPAWNING,
            RecoveryPhase.RESPAWNING: RecoveryPhase.AT_TEMPLE,
            RecoveryPhase.AT_TEMPLE: RecoveryPhase.RETURNING_TO_HUNT,
            RecoveryPhase.RE_EQUIPPING: RecoveryPhase.REBUFFING,
            RecoveryPhase.REBUFFING: RecoveryPhase.RETURNING_TO_HUNT,
            RecoveryPhase.RETURNING_TO_HUNT: RecoveryPhase.RECOVERED,
        }
        next_phase = transitions.get(self.phase, RecoveryPhase.RECOVERED)
        self.phase = next_phase
        self._phase_start = time.time()

    @property
    def should_change_area(self) -> bool:
        """Suggest area change if dying too often."""
        return self.consecutive_deaths >= 3

    @property
    def avg_recovery_time(self) -> float:
        if self.total_recoveries == 0:
            return 0
        return self.total_recovery_time / self.total_recoveries

    @property
    def stats(self) -> dict:
        return {
            "total_recoveries": self.total_recoveries,
            "consecutive_deaths": self.consecutive_deaths,
            "avg_recovery_time": round(self.avg_recovery_time, 1),
            "recovery_active": self.recovery_active,
            "current_phase": self.phase.name,
        }
