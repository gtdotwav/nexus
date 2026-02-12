"""
NEXUS — Textual TUI Dashboard

Primary local interface for the NEXUS gaming agent.
Runs in the terminal, zero browser required.

Architecture:
    - 3 screens: GameSelect (F1), Monitor (F2), Skills (F3)
    - Data flow: EventBus subscription + GameState polling (250ms)
    - Demo mode when agent=None (stable incremental simulation)
    - Thread-safe event buffer for cross-thread agent events

Usage:
    nexus start          → TUI as default interface
    nexus start --no-tui → headless (no TUI)
"""

from __future__ import annotations

import threading
import time
from typing import Optional, TYPE_CHECKING

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Grid
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.timer import Timer
from rich.text import Text

from dashboard.tui_models import TUIState, DemoSimulator
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
    layout: horizontal;
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
    margin-right: 1;
}

/* ── Monitor layout ── */
#monitor-grid {
    layout: grid;
    grid-size: 3 2;
    grid-columns: 1fr 2fr 1fr;
    grid-rows: 2fr 1fr;
    grid-gutter: 1;
    padding: 1;
    height: 1fr;
}

.panel {
    border: solid $accent;
    padding: 0 1;
    height: 100%;
}

/* ── Game select ── */
#game-select-wrapper {
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
}

/* ── Skills screen ── */
#skills-container {
    padding: 1 2;
    height: 100%;
}
"""


# ═══════════════════════════════════════════════════════
#  Screen: Game Select
# ═══════════════════════════════════════════════════════

class GameSelectScreen(Screen):
    """Select which game NEXUS should play."""

    BINDINGS = [
        Binding("f2", "app.switch_screen('monitor')", "Monitor", show=True),
        Binding("f3", "app.switch_screen('skills')", "Skills", show=True),
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
        yield Footer()

    @on(GameCard.Selected)
    def on_game_selected(self, event: GameCard.Selected) -> None:
        """A ready game card was clicked — switch to monitor."""
        app = self.app
        if isinstance(app, NexusTUI):
            app._game = event.game_id
            app.switch_screen("monitor")


# ═══════════════════════════════════════════════════════
#  Screen: Monitor
# ═══════════════════════════════════════════════════════

class MonitorScreen(Screen):
    """Main monitoring dashboard with real-time data."""

    BINDINGS = [
        Binding("f1", "app.switch_screen('game_select')", "Games", show=True),
        Binding("f3", "app.switch_screen('skills')", "Skills", show=True),
        Binding("p", "toggle_pause", "Pause", show=True),
        Binding("d", "toggle_demo", "Demo", show=True),
    ]

    def compose(self) -> ComposeResult:
        # Custom header
        with Horizontal(id="nexus-header"):
            yield Static("[bold cyan]NEXUS[/bold cyan] v0.4.2", id="header-title")
            yield ModeIndicator(id="header-mode")
            yield Static("⏱ 0:00:00", id="header-uptime")
            yield Static("[green]● LIVE[/green]", id="header-status")

        # 3x2 grid layout
        with Grid(id="monitor-grid"):
            # Row 1: Vitals | Events | Battle
            with Vertical(id="panel-vitals", classes="panel"):
                yield VitalBar(label="HP", style_type="hp", id="bar-hp")
                yield VitalBar(label="MP", style_type="mana", id="bar-mana")
                yield Static("", id="spacer-vitals")
                yield ModeIndicator(id="mode-display")
                yield ThreatIndicator(id="threat-display")
                yield Static("", id="position-display")
                yield Static("", id="skill-display")

            with Vertical(id="panel-events", classes="panel"):
                yield Static(" [bold]Event Stream[/bold]", id="events-title")
                yield EventStream(id="event-stream")

            with Vertical(id="panel-battle", classes="panel"):
                yield Static(" [bold]Battle List[/bold]", id="battle-title")
                yield BattleListWidget(id="battle-list")

            # Row 2: Session | Brain | Consciousness
            with Vertical(id="panel-session", classes="panel"):
                yield SessionStats(id="session-stats")

            with Vertical(id="panel-brain", classes="panel"):
                yield BrainStats(id="brain-stats")

            with Vertical(id="panel-consciousness", classes="panel"):
                yield ConsciousnessPanel(id="consciousness-panel")

        yield Footer()

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

            # Active skill
            self.query_one("#skill-display", Static).update(
                Text.from_markup(f" Skill [dim]{state.active_skill}[/dim]")
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
            elif not state.is_alive:
                status_widget.update("[red]● DEAD[/red]")
            else:
                app = self.app
                demo = isinstance(app, NexusTUI) and app._demo_mode
                status_widget.update("[yellow]● DEMO[/yellow]" if demo else "[green]● LIVE[/green]")

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
            pass  # Widget may not be mounted yet during screen transitions

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
        Binding("f1", "app.switch_screen('game_select')", "Games", show=True),
        Binding("f2", "app.switch_screen('monitor')", "Monitor", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="skills-container"):
            yield Static("[bold cyan]Skills[/bold cyan]\n", id="skills-header")
            yield Static("", id="skills-content")
        yield Footer()

    def update_skills(self, agent=None) -> None:
        """Refresh skills list from agent or show demo data."""
        try:
            widget = self.query_one("#skills-content", Static)
        except Exception:
            return

        if agent and hasattr(agent, "skill_engine") and agent.skill_engine:
            lines = []
            skills = getattr(agent.skill_engine, "skills", {})
            for name, skill in skills.items():
                active = "►" if name == getattr(agent.state, "active_skill", None) else " "
                score = getattr(skill, "performance_score", 0)
                category = getattr(skill, "category", "?")
                version = getattr(skill, "version", "1.0")
                wps = len(getattr(skill, "waypoints", []))

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

        # Thread-safe event buffer (agent events come from agent thread)
        self._event_lock = threading.Lock()
        self._event_buffer: list[str] = []

        # Stable demo simulator (no flickering)
        self._demo_sim = DemoSimulator()

    def on_mount(self) -> None:
        """Called when app is ready."""
        # Start on game select if pure demo, monitor otherwise
        if self._demo_mode and self._config_path is None:
            self.push_screen("game_select")
        else:
            self.push_screen("monitor")

        # Start polling loop (250ms)
        self._poll_timer = self.set_interval(0.25, self._poll_state)

        # If we have a config but no agent yet, start one
        if self._config_path and not self.agent:
            self._start_agent()

    @work(thread=False)
    async def _start_agent(self) -> None:
        """Start the NEXUS agent in the background."""
        try:
            from core.agent import NexusAgent
            self.agent = NexusAgent(config_path=self._config_path)
            self._demo_mode = False

            # Subscribe to all events for the event stream
            if hasattr(self.agent, "event_bus"):
                self.agent.event_bus.on_any(self._on_agent_event)

            # Start optional web dashboard alongside TUI
            if self._with_dashboard:
                from dashboard.server import DashboardServer
                dashboard = DashboardServer(self.agent, port=self._dashboard_port)
                await dashboard.start()

            self._push_event("system: Agent starting...")
            await self.agent.start()

        except Exception as e:
            self._push_event(f"error: Agent failed — {e}")

    def _on_agent_event(self, event) -> None:
        """
        Callback for all agent events — feed into event stream.

        THREAD SAFETY: This may be called from the agent's thread,
        so we use a lock to protect _event_buffer.
        """
        try:
            etype = event.type.name.lower()
            data = event.data or {}

            # Format event for display
            if etype == "kill":
                text = f"kill: {data.get('creature', '?')}"
            elif etype == "death":
                text = f"death: {data.get('cause', '?')}"
            elif etype in ("hp_changed", "mana_changed", "state_updated", "frame_captured"):
                return  # Too frequent, skip
            elif etype == "mode_changed":
                new_mode = data.get("new", "?")
                if hasattr(new_mode, "name"):
                    new_mode = new_mode.name
                text = f"mode: {new_mode}"
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
                text = f"explore: started"
            elif etype == "exploration_stopped":
                text = f"explore: stopped"
            elif etype == "error":
                text = f"error: {str(data.get('message', '?'))[:40]}"
            elif etype in ("agent_started", "agent_stopping"):
                text = f"system: {etype.replace('_', ' ')}"
            else:
                text = f"{etype}: {str(data)[:30]}"

            self._push_event(text)

        except Exception:
            pass  # Never crash the event handler

    def _push_event(self, text: str) -> None:
        """Thread-safe append to event buffer."""
        with self._event_lock:
            self._event_buffer.insert(0, text)
            if len(self._event_buffer) > 50:
                self._event_buffer = self._event_buffer[:50]

    def _get_events(self) -> list[str]:
        """Thread-safe read of event buffer."""
        with self._event_lock:
            return self._event_buffer.copy()

    def _poll_state(self) -> None:
        """Poll agent state and push to active screen (every 250ms)."""
        try:
            if self._demo_mode or self.agent is None:
                # Stable demo: incremental mutations, no flickering
                state = self._demo_sim.tick()
                # Merge any real events (e.g., "system: Agent starting...")
                real_events = self._get_events()
                if real_events:
                    state.events = real_events + state.events[:20]
            else:
                state = TUIState.from_agent(self.agent)
                state.events = self._get_events()
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
        """Graceful shutdown: stop agent, then exit."""
        if self.agent:
            try:
                await self.agent.stop()
            except Exception:
                pass
        self.exit()
