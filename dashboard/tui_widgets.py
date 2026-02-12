"""
NEXUS — TUI Custom Widgets

Textual widgets for the NEXUS dashboard.
Each widget is self-contained and updates via refresh(state).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Static, Label, ListView, ListItem, DataTable
from textual.reactive import reactive
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.bar import Bar
from rich.console import Group

from dashboard.tui_models import TUIState


# ═══════════════════════════════════════════════════════
#  Vital Bars (HP / Mana)
# ═══════════════════════════════════════════════════════

class VitalBar(Static):
    """Animated HP or Mana bar with gradient coloring."""

    value: reactive[float] = reactive(100.0)
    label_text: reactive[str] = reactive("HP")
    bar_style: reactive[str] = reactive("green")

    def __init__(self, label: str = "HP", style_type: str = "hp", **kwargs):
        super().__init__(**kwargs)
        self.label_text = label
        self._style_type = style_type

    def _get_color(self, pct: float) -> str:
        if self._style_type == "mana":
            if pct > 60:
                return "dodger_blue1"
            elif pct > 30:
                return "blue"
            return "dark_blue"
        else:
            if pct > 60:
                return "green"
            elif pct > 30:
                return "yellow"
            return "red bold"

    def render(self) -> Text:
        pct = max(0, min(100, self.value))
        color = self._get_color(pct)
        filled = int(pct / 5)
        empty = 20 - filled
        bar = f"{'█' * filled}{'░' * empty}"
        return Text.from_markup(
            f" {self.label_text} [{color}]{bar}[/{color}] {pct:5.1f}%"
        )

    def update_value(self, val: float):
        self.value = val


# ═══════════════════════════════════════════════════════
#  Mode & Threat Indicators
# ═══════════════════════════════════════════════════════

MODE_COLORS = {
    "IDLE": "dim white",
    "HUNTING": "green",
    "FLEEING": "red bold",
    "LOOTING": "yellow",
    "NAVIGATING": "cyan",
    "TRADING": "magenta",
    "HEALING_CRITICAL": "red bold blink",
    "DEPOSITING": "blue",
    "REFILLING": "blue",
    "CREATING_SKILL": "magenta",
    "EXPLORING": "cyan bold",
    "PAUSED": "dim",
}

THREAT_COLORS = {
    "NONE": "green",
    "LOW": "yellow",
    "MEDIUM": "dark_orange",
    "HIGH": "red bold",
    "CRITICAL": "red bold blink",
}


class ModeIndicator(Static):
    """Shows current agent mode with colored badge."""

    mode: reactive[str] = reactive("IDLE")

    def render(self) -> Text:
        color = MODE_COLORS.get(self.mode, "white")
        return Text.from_markup(f" Mode  [{color}]● {self.mode}[/{color}]")


class ThreatIndicator(Static):
    """Shows current threat level."""

    threat: reactive[str] = reactive("NONE")

    def render(self) -> Text:
        color = THREAT_COLORS.get(self.threat, "white")
        icons = {"NONE": "◇", "LOW": "◆", "MEDIUM": "▲", "HIGH": "▲▲", "CRITICAL": "⚠ ▲▲▲"}
        icon = icons.get(self.threat, "?")
        return Text.from_markup(f" Threat [{color}]{icon} {self.threat}[/{color}]")


# ═══════════════════════════════════════════════════════
#  Battle List
# ═══════════════════════════════════════════════════════

class BattleListWidget(Static):
    """Shows creatures on screen with inline HP bars."""

    DEFAULT_CSS = """
    BattleListWidget {
        height: auto;
        min-height: 3;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._battle_list: list[dict] = []
        self._target: str | None = None

    def update_data(self, battle_list: list[dict], target: str | None = None):
        self._battle_list = battle_list
        self._target = target
        self.refresh()

    def render(self) -> Text:
        if not self._battle_list:
            return Text.from_markup(" [dim]No creatures[/dim]")

        lines = []
        for c in self._battle_list[:8]:
            name = c.get("name", "?")[:16]
            hp = c.get("hp", 0)
            dist = c.get("dist", 0)
            attacking = c.get("attacking", False)

            # HP color
            if hp > 60:
                hp_color = "green"
            elif hp > 30:
                hp_color = "yellow"
            else:
                hp_color = "red"

            # Target marker
            marker = "►" if name == self._target else " "
            atk = " ⚔" if attacking else ""

            filled = int(hp / 10)
            bar = "█" * filled + "░" * (10 - filled)
            lines.append(
                f" {marker} {name:<16} [{hp_color}]{bar}[/{hp_color}] {hp:4.0f}% d:{dist}{atk}"
            )

        return Text.from_markup("\n".join(lines))


# ═══════════════════════════════════════════════════════
#  Event Stream
# ═══════════════════════════════════════════════════════

class EventStream(Static):
    """Scrollable log of recent agent events."""

    DEFAULT_CSS = """
    EventStream {
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._events: list[str] = []

    def push_event(self, event: str):
        self._events.insert(0, event)
        if len(self._events) > 50:
            self._events = self._events[:50]
        self.refresh()

    def set_events(self, events: list[str]):
        self._events = events[:50]
        self.refresh()

    def render(self) -> Text:
        if not self._events:
            return Text.from_markup(" [dim]Waiting for events...[/dim]")

        lines = []
        for ev in self._events[:15]:
            # Color events by type
            if ev.startswith("kill:"):
                lines.append(f" [green]{ev}[/green]")
            elif ev.startswith("death:"):
                lines.append(f" [red bold]{ev}[/red bold]")
            elif ev.startswith("heal:"):
                lines.append(f" [cyan]{ev}[/cyan]")
            elif ev.startswith("loot:"):
                lines.append(f" [yellow]{ev}[/yellow]")
            elif ev.startswith("spot:"):
                lines.append(f" [magenta]{ev}[/magenta]")
            elif ev.startswith("mode:"):
                lines.append(f" [blue]{ev}[/blue]")
            else:
                lines.append(f" [dim]{ev}[/dim]")

        return Text.from_markup("\n".join(lines))


# ═══════════════════════════════════════════════════════
#  Session Stats
# ═══════════════════════════════════════════════════════

class SessionStats(Static):
    """XP/hr, Gold/hr, Kills, Deaths grid."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_stats(self, state: TUIState):
        self._data = {
            "xp_hr": state.xp_hr,
            "gold_hr": state.gold_hr,
            "kills": state.kills,
            "deaths": state.deaths,
            "duration": state.duration_min,
            "close_calls": state.close_calls,
        }
        self.refresh()

    def _format_number(self, n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(n)

    def render(self) -> Text:
        d = self._data
        if not d:
            return Text.from_markup(" [dim]No session data[/dim]")

        xp = self._format_number(d.get("xp_hr", 0))
        gold = self._format_number(d.get("gold_hr", 0))
        kills = d.get("kills", 0)
        deaths = d.get("deaths", 0)
        dur = d.get("duration", 0)
        cc = d.get("close_calls", 0)

        hours = int(dur // 60)
        mins = int(dur % 60)

        return Text.from_markup(
            f" [bold]Session[/bold] {hours}h{mins:02d}m\n"
            f" XP/hr   [cyan]{xp}[/cyan]\n"
            f" Gold/hr [yellow]{gold}[/yellow]\n"
            f" Kills   [green]{kills}[/green]\n"
            f" Deaths  [red]{deaths}[/red]\n"
            f" Close   [dark_orange]{cc}[/dark_orange]"
        )


# ═══════════════════════════════════════════════════════
#  Brain Stats
# ═══════════════════════════════════════════════════════

CB_COLORS = {
    "CLOSED": "green",
    "HALF_OPEN": "yellow",
    "OPEN": "red bold",
}


class BrainStats(Static):
    """Strategic brain metrics: calls, latency, errors, circuit breaker."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_stats(self, state: TUIState):
        self._data = {
            "calls": state.brain_calls,
            "latency": state.brain_latency_ms,
            "error_rate": state.brain_error_rate,
            "skipped": state.brain_skipped,
            "cb": state.circuit_breaker,
        }
        self.refresh()

    def render(self) -> Text:
        d = self._data
        if not d:
            return Text.from_markup(" [dim]No brain data[/dim]")

        cb = d.get("cb", "CLOSED")
        cb_color = CB_COLORS.get(cb, "white")
        lat = d.get("latency", 0)
        lat_color = "green" if lat < 300 else ("yellow" if lat < 800 else "red")
        err = d.get("error_rate", 0) * 100

        return Text.from_markup(
            f" [bold]Strategic Brain[/bold]\n"
            f" Calls   {d.get('calls', 0)}\n"
            f" Latency [{lat_color}]{lat}ms[/{lat_color}]\n"
            f" Errors  {err:.1f}%\n"
            f" Skip    {d.get('skipped', 0)}\n"
            f" CB      [{cb_color}]{cb}[/{cb_color}]"
        )


# ═══════════════════════════════════════════════════════
#  Consciousness Panel
# ═══════════════════════════════════════════════════════

EMOTION_ICONS = {
    "Focused": "🎯", "Confident": "💪", "Cautious": "👀",
    "Excited": "⚡", "Alert": "🔔", "Anxious": "😰",
    "Frustrated": "😤", "Satisfied": "😊", "Bored": "😴",
}


class ConsciousnessPanel(Static):
    """Emotion, goals, recent memories."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._emotion: str = ""
        self._goals: list[dict] = []
        self._memories: list[dict] = []

    def update_data(self, state: TUIState):
        self._emotion = state.emotion
        self._goals = state.goals
        self._memories = state.memories
        self.refresh()

    def render(self) -> Text:
        lines = [" [bold]Consciousness[/bold]"]

        if self._emotion:
            icon = EMOTION_ICONS.get(self._emotion, "🧠")
            lines.append(f" {icon} [italic]{self._emotion}[/italic]")

        if self._goals:
            lines.append(" [dim]Goals:[/dim]")
            for g in self._goals[:3]:
                lines.append(f"  • {g.get('text', '?')[:40]}")

        if self._memories:
            lines.append(" [dim]Memory:[/dim]")
            for m in self._memories[:2]:
                lines.append(f"  ◦ {m.get('text', '?')[:40]}")

        if len(lines) == 1:
            lines.append(" [dim]No consciousness data[/dim]")

        return Text.from_markup("\n".join(lines))


# ═══════════════════════════════════════════════════════
#  Game Card (for game selection screen)
# ═══════════════════════════════════════════════════════

class GameCard(Static):
    """Selectable card for a game in the selection screen."""

    DEFAULT_CSS = """
    GameCard {
        width: 36;
        height: 10;
        border: solid $accent;
        padding: 1 2;
        margin: 1;
    }
    GameCard:hover {
        border: double $accent;
    }
    GameCard.-ready {
        border: solid green;
    }
    GameCard.-coming-soon {
        border: solid $surface;
        opacity: 0.6;
    }
    """

    def __init__(self, game_id: str, name: str, genre: str, description: str, ready: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.game_id = game_id
        self._name = name
        self._genre = genre
        self._description = description
        self._ready = ready
        if ready:
            self.add_class("-ready")
        else:
            self.add_class("-coming-soon")

    def render(self) -> Text:
        status = "[green]● READY[/green]" if self._ready else "[dim]○ COMING SOON[/dim]"
        return Text.from_markup(
            f"[bold]{self._name}[/bold]\n"
            f"[dim]{self._genre}[/dim]\n\n"
            f"{self._description[:60]}\n\n"
            f"{status}"
        )
