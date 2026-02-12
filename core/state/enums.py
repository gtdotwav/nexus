"""NEXUS — Game state enumerations."""

from enum import Enum, auto


class AgentMode(Enum):
    IDLE = auto()
    HUNTING = auto()
    FLEEING = auto()
    LOOTING = auto()
    NAVIGATING = auto()
    TRADING = auto()
    HEALING_CRITICAL = auto()
    DEPOSITING = auto()
    REFILLING = auto()
    CREATING_SKILL = auto()
    EXPLORING = auto()
    PAUSED = auto()


class ThreatLevel(Enum):
    NONE = auto()
    LOW = auto()       # Unknown player nearby
    MEDIUM = auto()    # Player following or approaching
    HIGH = auto()      # Player attacking / skull on
    CRITICAL = auto()  # Multiple PKs, trapped
