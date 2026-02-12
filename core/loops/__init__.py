"""
NEXUS — Agent Loops Package

Each loop is a separate file with a single async function:
    async def run(agent: 'NexusAgent') -> None

This allows multiple devs to work on different loops
without touching agent.py or each other's code.

STARTUP CHECK:
    On import, this module warns if there are .py files in core/loops/
    that aren't registered in ALL_LOOPS. This catches the common mistake
    of creating a new loop file but forgetting to register it.
"""

import os
import structlog

log = structlog.get_logger()

from core.loops.perception import run as perception_loop
from core.loops.reactive import run as reactive_loop
from core.loops.action import run as action_loop
from core.loops.strategic import run as strategic_loop
from core.loops.consciousness import run as consciousness_loop
from core.loops.evolution import run as evolution_loop
from core.loops.recovery import run as recovery_loop
from core.loops.reasoning import run as reasoning_loop
from core.loops.metrics import run as metrics_loop

ALL_LOOPS = [
    ("perception", perception_loop),
    ("reactive", reactive_loop),
    ("actions", action_loop),
    ("strategic", strategic_loop),
    ("consciousness", consciousness_loop),
    ("evolution", evolution_loop),
    ("recovery", recovery_loop),
    ("reasoning", reasoning_loop),
    ("metrics", metrics_loop),
]

# ─── Auto-discovery check ──────────────────────────────────
# Warn about loop files that exist but aren't registered
_IGNORE_FILES = {"__init__.py", "TEMPLATE.py"}
_registered_modules = {
    "perception", "reactive", "action", "strategic",
    "consciousness", "evolution", "recovery", "reasoning", "metrics",
}

_loops_dir = os.path.dirname(os.path.abspath(__file__))
for _fname in os.listdir(_loops_dir):
    if _fname.endswith(".py") and _fname not in _IGNORE_FILES:
        _mod_name = _fname[:-3]  # strip .py
        if _mod_name not in _registered_modules:
            log.warning("loops.unregistered_file",
                        file=_fname,
                        hint=f"Add '{_mod_name}' to ALL_LOOPS in core/loops/__init__.py")

__all__ = [
    "ALL_LOOPS",
    "perception_loop",
    "reactive_loop",
    "action_loop",
    "strategic_loop",
    "consciousness_loop",
    "evolution_loop",
    "recovery_loop",
    "reasoning_loop",
    "metrics_loop",
]
