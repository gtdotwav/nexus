"""NEXUS Dashboard — TUI (primary) + Web (secondary) interfaces."""
from dashboard.server import DashboardServer
from dashboard.tui import NexusTUI

__all__ = ["DashboardServer", "NexusTUI"]
