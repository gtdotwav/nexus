"""
NEXUS — Textual TUI Dashboard

Primary local interface for the NEXUS gaming agent.
Runs in the terminal, zero browser required.

Architecture:
    - 3 screens: GameSelect (F1), Monitor (F2), Skills (F3)
    - Data flow: EventBus subscription + GameState polling (250ms)
    - Demo mode when agent=None (simulated data for preview)

Usage:
    nexus start          → TUI as default interface
    nexus start --no-tui → headless (no TUI)
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, TYPE_CHECKING

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container, Grid
from textual.screen import Screen
from textual.widgets import Static, Header, Footer, Label, Button, Placeholder
from textual.timer import Timer
from rich.text import Text

from dashboard.tui_models import TUIState
from dashboard.tui_widgets import (
    VitalBar,
    ModeIndicator,
    ThreatIndicator,
    BattleListWidget,
    EventStream,
    SessionStats,
    BrainStats,
    ConsciousnessPanel,
    GameCard,
)

if TYPE_CHECKING:
    from core.agent import NexusAgent


# ═══════════════════════════════════════════════════════
#  CSS Theme
# ═══════════════════════════════════════════════════════

NEXUS_CSS = """
Screen {
    background: $surface;
}

/* ── Header bar ── */
#nexus-header {
    dock: top;
    height: 3;
    background: $boost;
    color: $text;
    padding: 0 2;
}

#header-title {
    width: auto;
    color: cyan;
    text-style: bold;
}

#header-mode {
    width: auto;
    margin: 0 2;
}

#header-uptime {
    width: auto;
    color: $text-muted;
}

#header-status {
    width: auto;
    dock: right;
    color: green;
}

/* ── Monitor layout ── */
#monitor-grid {
    layout: grid;
    grid-size: 3 2;
    grid-columns: 1fr 2fr 1fr;
    grid-rows: 2fr 1fr;
    grid-gutter: 1;
    padding: 1;
    height: 100%;
}

.panel {
    border: solid $accent;
    padding: 0 1;
    height: 100%;
}

#panel-vitals {
    row-span: 1;
}

#panel-events {
    row-span: 1;
}

#panel-battle {
    row-span: 1;
}

#panel-session {
    row-span: 1;
}

#panel-brain {
    row-span: 1;
}

#panel-consciousness {
    row-span: 1;
}

/* ── Game select ── */
#game-select-container {
    align: center middle;
    width: 100%;
    height: 100%;
}

#game-grid {
    layout: horizontal;
    align: center middle;
    height: auto;
    width: auto;
}

#game-select-title {
    text-align: center;
    width: 100%;
    margin-bottom: 2;
    text-style: bold;
    color: cyan;
}

/* ── Skills screen ── */
#skills-container {
    padding: 1 2;
    height: 100%;
}

#skills-table {
    height: 100%;
}

/* ── Footer keybinds ── */
#nexus-footer {
    dock: bottom;
    height: 1;
    background: $boost;
}
"""


# ═══════════════════════════════════════════════════════
#  Screen: Game Select
# ═══════════════════════════════════════════════════════

class GameSelectScreen(Screen):
    """Select which game NEXUS should play."""

    BINDINGS = [
        Binding("f2", "switch_monitor", "Monitor", show=True),
        Binding("f3", "switch_skills", "Skills", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]"
            "    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗\n"
            "    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝\n"
            "    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗\n"
            "    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║\n"
            "    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║\n"
            "    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝\n"
            "[/bold cyan]\n"
            "    [dim]Select a game to start the agent[/dim]\n",
            id="game-select-title",
        )
        with Horizontal(id="game-grid"):
            yield GameCard(
                game_id="tibia",
                name="Tibia",
                genre="MMORPG · Isometric",
                description="Full support: hunting, looting, navigation, anti-PK",
                ready=True,
            )
            yield GameCard(
                game_id="lost_ark",
                name="Lost Ark",
                genre="ARPG · Isometric",
                description="Chaos dungeon farming, daily quests",
                ready=False,
            )
            yield GameCard(
                game_id="poe",
                name="Path of Exile",
                genre="ARPG · Isometric",
                description="Map farming, flask management",
                ready=False,
            )

    @on(GameCard)
    def on_game_card_click(self, event) -> None:
        pass  # Handled via click on the card widget

    def action_switch_monitor(self) -> None:
        self.app.switch_screen("monitor")

    def action_switch_skills(self) -> None:
        self.app.switch_screen("skills")


# ═══════════════════════════════════════════════════════
#  Screen: Monitor
# ═══════════════════════════════════════════════════════

class MonitorScreen(Screen):
    """Main monitoring dashboard with real-time data."""

    BINDINGS = [
        Binding("f1", "switch_games", "Games", show=True),
        Binding("f3", "switch_skills", "Skills", show=True),
        Binding("p", "toggle_pause", "Pause", show=True),
        Binding("d", "toggle_demo", "Demo", show=True),
    ]

    def compose(self) -> ComposeResult:
        # Header
        with Horizontal(id="nexus-header"):
            yield Static("[bold cyan]NEXUS[/bold cyan] v0.4.2", id="header-title")
            yield ModeIndicator(id="header-mode")
            yield Static("⏱ 0:00:00", id="header-uptime")
            yield Static("[green]● CONNECTED[/green]", id="header-status")

        # 3x2 grid
        with Grid(id="monitor-grid"):
            # Row 1
            with Vertical(id="panel-vitals", classes="panel"):
                yield VitalBar(label="HP", style_type="hp", id="bar-hp")
                yield VitalBar(label="MP", style_type="mana", id="bar-mana")
                yield Static("", id="spacer-vitals")
                yield ModeIndicator(id="mode-display")
                yield ThreatIndicator(id="threat-display")
                yield Static("", id="position-display")

            with Vertical(id="panel-events", classes="panel"):
                yield Static(" [bold]Event Stream[/bold]", id="events-title")
                yield EventStream(id="event-stream")

            with Vertical(id="panel-battle", classes="panel"):
                yield Static(" [bold]Battle List[/bold]", id="battle-title")
                yield BattleListWidget(id="battle-list")

            # Row 2
            with Vertical(id="panel-session", classes="panel"):
                yield SessionStats(id="session-stats")

            with Vertical(id="panel-brain", classes="panel"):
                yield BrainStats(id="brain-stats")

            with Vertical(id="panel-consciousness", classes="panel"):
                yield ConsciousnessPanel(id="consciousness-panel")

    def update_state(self, state: TUIState) -> None:
        """Push new state to all widgets."""
        try:
            # Vitals
            self.query_one("#bar-hp", VitalBar).update_value(state.hp)
            self.query_one("#bar-mana", VitalBar).update_value(state.mana)

            # Mode & Threat
            self.query_one("#header-mode", ModeIndicator).mode = state.mode
            self.query_one("#mode-display", ModeIndicator).mode = state.mode
            self.query_one("#threat-display", ThreatIndicator).threat = state.threat

            # Position
            x, y, z = state.position
            self.query_one("#position-display", Static).update(
                Text.from_markup(f" Pos [cyan]({x}, {y}, {z})[/cyan]")
            )

            # Uptime
            secs = state.uptime_seconds or int(state.duration_min * 60)
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            self.query_one("#header-uptime", Static).update(f"⏱ {h}:{m:02d}:{s:02d}")

            # Status indicator
            status_widget = self.query_one("#header-status", Static)
            if state.circuit_breaker == "OPEN":
                status_widget.update("[red]● CB OPEN[/red]")
            elif state.threat in ("HIGH", "CRITICAL"):
                status_widget.update(f"[red]● THREAT {state.threat}[/red]")
            else:
                status_widget.update("[green]● CONNECTED[/green]")

            # Events
            self.query_one("#event-stream", EventStream).set_events(state.events)

            # Battle
            self.query_one("#battle-list", BattleListWidget).update_data(
                state.battle_list, state.target
            )

            # Stats panels
            self.query_one("#session-stats", SessionStats).update_stats(state)
            self.query_one("#brain-stats", BrainStats).update_stats(state)
            self.query_one("#consciousness-panel", ConsciousnessPanel).update_data(state)

        except Exception:
            pass  # Widget may not be mounted yet

    def action_switch_games(self) -> None:
        self.app.switch_screen("game_select")

    def action_switch_skills(self) -> None:
        self.app.switch_screen("skills")

    def action_toggle_pause(self) -> None:
        app = self.app
        if isinstance(app, NexusTUI) and app.agent:
            from core.state.enums import AgentMode
            if app.agent.state.mode == AgentMode.PAUSED:
                app.agent.state.set_mode(AgentMode.HUNTING)
            else:
                app.agent.state.set_mode(AgentMode.PAUSED)

    def action_toggle_demo(self) -> None:
        app = self.app
        if isinstance(app, NexusTUI):
            app._demo_mode = not app._demo_mode


# ═══════════════════════════════════════════════════════
#  Screen: Skills
# ═══════════════════════════════════════════════════════

class SkillsScreen(Screen):
    """View loaded skills with their performance data."""

    BINDINGS = [
        Binding("f1", "switch_games", "Games", show=True),
        Binding("f2", "switch_monitor", "Monitor", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="skills-container"):
            yield Static("[bold cyan]Skills[/bold cyan]", id="skills-header")
            yield Static("", id="skills-content")

    def update_skills(self, agent=None) -> None:
        """Refresh skills list from agent or show demo data."""
        widget = self.query_one("#skills-content", Static)

        if agent and hasattr(agent, "skill_engine"):
            lines = []
            for name, skill in agent.skill_engine.skills.items():
                active = "►" if name == agent.state.active_skill else " "
                score = getattr(skill, "performance_score", 0)
                category = getattr(skill, "category", "?")
                version = getattr(skill, "version", "1.0")
                wps = len(getattr(skill, "waypoints", []))

                # Score color
                if score >= 80:
                    sc = f"[green]{score:.0f}[/green]"
                elif score >= 50:
                    sc = f"[yellow]{score:.0f}[/yellow]"
                else:
                    sc = f"[red]{score:.0f}[/red]"

                lines.append(
                    f" {active} [bold]{name:<25}[/bold] {category:<12} Score: {sc}  WPs: {wps:<4} v{version}"
                )

            if lines:
                widget.update(Text.from_markup("\n".join(lines)))
            else:
                widget.update(Text.from_markup(" [dim]No skills loaded[/dim]"))
        else:
            # Demo data
            demo_skills = [
                ("rotworm_hunt_v3", "hunting", 87, 12, "3.0", True),
                ("cyclops_camp_safe", "hunting", 72, 8, "2.1", False),
                ("depot_restock", "supply", 95, 6, "1.0", False),
                ("pk_escape_route", "safety", 60, 4, "1.0", False),
            ]
            lines = []
            for name, cat, score, wps, ver, active in demo_skills:
                marker = "►" if active else " "
                if score >= 80:
                    sc = f"[green]{score}[/green]"
                elif score >= 50:
                    sc = f"[yellow]{score}[/yellow]"
                else:
                    sc = f"[red]{score}[/red]"
                lines.append(
                    f" {marker} [bold]{name:<25}[/bold] {cat:<12} Score: {sc}  WPs: {wps:<4} v{ver}"
                )
            widget.update(Text.from_markup("\n".join(lines) + "\n\n [dim](Demo mode)[/dim]"))

    def action_switch_games(self) -> None:
        self.app.switch_screen("game_select")

    def action_switch_monitor(self) -> None:
        self.app.switch_screen("monitor")


# ═══════════════════════════════════════════════════════
#  Main App
# ═══════════════════════════════════════════════════════

class NexusTUI(App):
    """
    NEXUS Terminal User Interface.

    The primary local interface for the NEXUS gaming agent.
    Runs Textual in the same async loop as the agent.
    """

    CSS = NEXUS_CSS
    TITLE = "NEXUS"
    SUB_TITLE = "Autonomous Gaming Agent"

    BINDINGS = [
        Binding("f1", "switch_screen('game_select')", "Games", show=True),
        Binding("f2", "switch_screen('monitor')", "Monitor", show=True),
        Binding("f3", "switch_screen('skills')", "Skills", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    SCREENS = {
        "game_select": GameSelectScreen,
        "monitor": MonitorScreen,
        "skills": SkillsScreen,
    }

    def __init__(
        self,
        agent: Optional["NexusAgent"] = None,
        config_path: Optional[str] = None,
        game: str = "tibia",
        with_dashboard: bool = False,
        dashboard_port: int = 8420,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.agent = agent
        self._config_path = config_path
        self._game = game
        self._with_dashboard = with_dashboard
        self._dashboard_port = dashboard_port
        self._demo_mode = agent is None
        self._poll_timer: Optional[Timer] = None
        self._start_time = time.time()
        self._event_buffer: list[str] = []

    def on_mount(self) -> None:
        """Called when app is ready. Start agent if config provided."""
        # Start on monitor screen (or game select if no agent)
        if self._demo_mode and self._config_path is None:
            self.push_screen("game_select")
        else:
            self.push_screen("monitor")

        # Start polling loop
        self._poll_timer = self.set_interval(0.25, self._poll_state)

        # If we have a config but no agent, create one
        if self._config_path and not self.agent:
            self._start_agent()

    @work(thread=False)
    async def _start_agent(self) -> None:
        """Start the NEXUS agent in background."""
        try:
            from core.agent import NexusAgent
            self.agent = NexusAgent(config_path=self._config_path)
            self._demo_mode = False

            # Subscribe to all events for the event stream
            if hasattr(self.agent, "event_bus"):
                self.agent.event_bus.on_any(self._on_agent_event)

            # Start optional web dashboard
            if self._with_dashboard:
                from dashboard.server import DashboardServer
                dashboard = DashboardServer(self.agent, port=self._dashboard_port)
                await dashboard.start()

            await self.agent.start()

        except Exception as e:
            self._event_buffer.insert(0, f"[red]Agent error: {e}[/red]")

    def _on_agent_event(self, event) -> None:
        """Callback for all agent events — feed into event stream."""
        try:
            etype = event.type.name.lower()
            data = event.data or {}

            # Format event for display
            if etype == "kill":
                text = f"kill: {data.get('creature', '?')}"
            elif etype == "death":
                text = f"death: {data.get('cause', '?')}"
            elif etype in ("hp_changed", "mana_changed"):
                return  # Too frequent, skip
            elif etype == "mode_changed":
                text = f"mode: {data.get('new', '?')}"
            elif etype == "creature_spotted":
                text = f"spot: {data.get('name', '?')}"
            elif etype == "player_spotted":
                text = f"player: {data.get('name', '?')}"
            elif etype == "skill_activated":
                text = f"skill: {data.get('name', '?')}"
            elif etype == "strategic_decision":
                text = f"brain: {data.get('action', 'decision')}"
            elif etype == "close_call":
                text = f"CLOSE CALL: HP {data.get('hp', '?')}%"
            elif etype == "exploration_started":
                text = f"explore: started ({data.get('strategy', '?')})"
            elif etype == "exploration_stopped":
                text = f"explore: stopped"
            elif etype == "error":
                text = f"error: {data.get('message', '?')[:40]}"
            else:
                text = f"{etype}: {str(data)[:40]}"

            self._event_buffer.insert(0, text)
            if len(self._event_buffer) > 50:
                self._event_buffer = self._event_buffer[:50]

        except Exception:
            pass  # Never crash the event handler

    def _poll_state(self) -> None:
        """Poll agent state and push to active screen (every 250ms)."""
        try:
            # Build state
            if self._demo_mode or self.agent is None:
                state = TUIState.demo()
                state.events = self._event_buffer if self._event_buffer else state.events
            else:
                state = TUIState.from_agent(self.agent)
                state.events = self._event_buffer
                state.uptime_seconds = int(time.time() - self._start_time)

            # Push to active screen
            active = self.screen
            if isinstance(active, MonitorScreen):
                active.update_state(state)
            elif isinstance(active, SkillsScreen):
                active.update_skills(self.agent)

        except Exception:
            pass  # Polling must never crash

    async def action_quit(self) -> None:
        """Graceful shutdown."""
        if self.agent:
            try:
                await self.agent.stop()
            except Exception:
                pass
        self.exit()

    def on_game_card_pressed(self, event) -> None:
        """Handle game card selection from GameSelectScreen."""
        pass  # Future: start agent with selected game

    @on(GameCard)
    def handle_game_click(self, event) -> None:
        """When a game card is clicked."""
        pass  # Placeholder for future game selection logic
