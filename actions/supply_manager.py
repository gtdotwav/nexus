"""
NEXUS Agent — Supply Manager

Monitors consumable supplies and triggers depot runs when needed.

Responsibilities:
- Track current supply counts (health potions, mana potions, runes, food)
- Compare against skill-defined thresholds
- Trigger depot run when any supply falls below threshold
- Execute depot sequence: navigate → deposit loot → refill → return
- Manage gold/cap constraints
"""

from __future__ import annotations

import asyncio
import time
import structlog
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import GameState

log = structlog.get_logger()


class DepotPhase(Enum):
    """Phases of a depot run."""
    NONE = auto()
    WALKING_TO_DEPOT = auto()
    DEPOSITING_LOOT = auto()
    BUYING_SUPPLIES = auto()
    SELLING_LOOT = auto()
    RETURNING_TO_HUNT = auto()


@dataclass
class SupplyRule:
    """Rule for when to trigger depot run."""
    item: str
    below: int = 0          # Trigger when count goes below this
    condition: str = ""      # Alternative: "cap_below_100"
    priority: int = 0        # Higher = more urgent


class SupplyManager:
    """
    Tracks supplies and orchestrates depot runs.

    Flow:
        1. Monitor → check supplies every 10s
        2. Alert → when any threshold is breached
        3. Navigate → switch to depot waypoints
        4. Deposit → put loot in depot
        5. Buy → purchase supplies from NPC
        6. Return → navigate back to hunt area

    The supply manager doesn't execute the actual NPC interactions —
    it signals the mode change and coordinates the phases.
    """

    def __init__(self, state: "GameState", config: dict):
        self.state = state
        self.config = config

        # Supply rules (loaded from skill config)
        self.bring_list: list[dict] = []
        self.leave_when: list[SupplyRule] = []
        self.depot_actions: list[str] = []

        # Depot run state
        self.phase: DepotPhase = DepotPhase.NONE
        self.depot_run_active: bool = False
        self._phase_start: float = 0
        self._phase_timeout: float = 120  # Max 2min per phase

        # Tracking
        self._last_check: float = 0
        self._check_interval: float = 10.0  # Check every 10s
        self.depot_runs: int = 0
        self._supply_history: list[dict] = []

    def load_supply_config(self, supply_config: dict):
        """Load supply configuration from active skill."""
        self.bring_list = supply_config.get("bring", [])
        self.depot_actions = supply_config.get("depot_actions", [])

        # Parse leave_when rules
        self.leave_when = []
        for rule in supply_config.get("leave_when", []):
            if isinstance(rule, dict):
                self.leave_when.append(SupplyRule(
                    item=rule.get("item", ""),
                    below=rule.get("below", 0),
                    condition=rule.get("condition", ""),
                ))

        log.info("supplies.config_loaded",
                 bring=len(self.bring_list),
                 rules=len(self.leave_when))

    def check_supplies(self) -> Optional[dict]:
        """
        Check current supplies against thresholds.
        Returns dict with triggered rules, or None if all OK.
        """
        now = time.time()
        if now - self._last_check < self._check_interval:
            return None
        self._last_check = now

        triggered = []
        supplies = self.state.supplies

        for rule in self.leave_when:
            if rule.condition:
                # Condition-based rule
                if rule.condition == "cap_below_100" and self.state.cap < 100:
                    triggered.append({
                        "rule": "cap_below_100",
                        "current": self.state.cap,
                        "threshold": 100,
                    })
            elif rule.item:
                # Item count rule
                current_count = getattr(supplies, rule.item.replace(" ", "_"), 0)
                if current_count <= rule.below:
                    triggered.append({
                        "rule": rule.item,
                        "current": current_count,
                        "threshold": rule.below,
                    })

        if triggered:
            log.info("supplies.threshold_breached", rules=triggered)
            return {"triggered": triggered, "action": "depot_run"}

        return None

    def should_depot(self) -> bool:
        """Quick check: should we initiate a depot run?"""
        result = self.check_supplies()
        return result is not None

    async def start_depot_run(self):
        """Begin depot run sequence."""
        if self.depot_run_active:
            return

        self.depot_run_active = True
        self.depot_runs += 1
        self.phase = DepotPhase.WALKING_TO_DEPOT
        self._phase_start = time.time()

        log.info("supplies.depot_run_started", run_number=self.depot_runs)

    async def tick(self) -> Optional[str]:
        """
        Process one supply manager tick. Returns current phase action.

        During a depot run, this manages the phase transitions.
        Outside of depot run, it monitors supply levels.
        """
        if not self.depot_run_active:
            # Just monitor
            check = self.check_supplies()
            if check:
                return "needs_depot"
            return None

        # Phase timeout protection
        elapsed = time.time() - self._phase_start
        if elapsed > self._phase_timeout:
            log.warning("supplies.phase_timeout", phase=self.phase.name)
            self._advance_phase()

        return self.phase.name.lower()

    def notify_arrived_at_depot(self):
        """Called when navigator reaches depot waypoint."""
        if self.phase == DepotPhase.WALKING_TO_DEPOT:
            self.phase = DepotPhase.DEPOSITING_LOOT
            self._phase_start = time.time()
            log.info("supplies.arrived_at_depot")

    def notify_deposit_complete(self):
        """Called after loot is deposited."""
        if self.phase == DepotPhase.DEPOSITING_LOOT:
            self.phase = DepotPhase.BUYING_SUPPLIES
            self._phase_start = time.time()
            log.info("supplies.deposit_complete")

    def notify_supplies_bought(self):
        """Called after supplies are purchased."""
        if self.phase == DepotPhase.BUYING_SUPPLIES:
            self.phase = DepotPhase.RETURNING_TO_HUNT
            self._phase_start = time.time()
            log.info("supplies.supplies_bought")

    def notify_returned_to_hunt(self):
        """Called when back at hunting area."""
        self.depot_run_active = False
        self.phase = DepotPhase.NONE
        log.info("supplies.depot_run_complete", run_number=self.depot_runs)

    def _advance_phase(self):
        """Force advance to next phase (timeout recovery)."""
        transitions = {
            DepotPhase.WALKING_TO_DEPOT: DepotPhase.DEPOSITING_LOOT,
            DepotPhase.DEPOSITING_LOOT: DepotPhase.BUYING_SUPPLIES,
            DepotPhase.BUYING_SUPPLIES: DepotPhase.RETURNING_TO_HUNT,
            DepotPhase.RETURNING_TO_HUNT: DepotPhase.NONE,
        }
        next_phase = transitions.get(self.phase, DepotPhase.NONE)
        log.info("supplies.phase_skip", old=self.phase.name, new=next_phase.name)
        self.phase = next_phase
        self._phase_start = time.time()

        if next_phase == DepotPhase.NONE:
            self.depot_run_active = False

    @property
    def stats(self) -> dict:
        return {
            "depot_runs": self.depot_runs,
            "depot_run_active": self.depot_run_active,
            "current_phase": self.phase.name,
        }
