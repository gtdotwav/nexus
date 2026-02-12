"""
NEXUS — Agent Loops Package

Each loop is a separate file with a single async function:
    async def run(agent: 'NexusAgent') -> None

This allows multiple devs to work on different loops
without touching agent.py or each other's code.
"""

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
