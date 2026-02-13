#!/usr/bin/env python3
"""
NEXUS — First-Run Setup Wizard

Interactive setup that guides new users through:
    1. Game selection
    2. Character configuration
    3. API key setup
    4. Screen calibration
    5. Hotkey configuration
    6. Dashboard preferences

Creates ~/.nexus/config.yaml with all settings.
"""

from __future__ import annotations

import os
import sys
import yaml
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

NEXUS_HOME = Path.home() / ".nexus"
CONFIG_PATH = NEXUS_HOME / "config.yaml"


class SetupWizard:
    """Interactive setup wizard for NEXUS."""

    def __init__(self):
        self.console = Console() if HAS_RICH else None
        self.config: dict = {}

    def print(self, text: str = "", style: str = ""):
        if self.console:
            self.console.print(text, style=style)
        else:
            # Strip rich markup for plain terminal
            import re
            clean = re.sub(r'\[.*?\]', '', text)
            print(clean)

    def ask(self, prompt: str, default: str = "") -> str:
        if HAS_RICH:
            return Prompt.ask(f"  {prompt}", default=default or None) or default
        else:
            suffix = f" [{default}]" if default else ""
            result = input(f"  {prompt}{suffix}: ").strip()
            return result or default

    def ask_int(self, prompt: str, default: int = 0) -> int:
        if HAS_RICH:
            return IntPrompt.ask(f"  {prompt}", default=default)
        else:
            try:
                result = input(f"  {prompt} [{default}]: ").strip()
                return int(result) if result else default
            except ValueError:
                return default

    def confirm(self, prompt: str, default: bool = True) -> bool:
        if HAS_RICH:
            return Confirm.ask(f"  {prompt}", default=default)
        else:
            suffix = " [Y/n]" if default else " [y/N]"
            result = input(f"  {prompt}{suffix}: ").strip().lower()
            if not result:
                return default
            return result in ("y", "yes")

    def choose(self, prompt: str, options: list[str], default: str = "") -> str:
        self.print(f"\n  {prompt}")
        for i, opt in enumerate(options, 1):
            marker = "[cyan]→[/cyan]" if opt == default else " "
            self.print(f"    {marker} {i}. {opt}")

        while True:
            choice = self.ask("Choice (number)", default=str(options.index(default) + 1) if default else "1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                if choice in options:
                    return choice
            self.print("  [red]Invalid choice, try again.[/red]")

    # ═══════════════════════════════════════════════════════
    #  Wizard Steps
    # ═══════════════════════════════════════════════════════

    def step_welcome(self):
        """Welcome screen."""
        self.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
        self.print("[bold cyan]  NEXUS — First-Time Setup[/bold cyan]")
        self.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")

        self.print("  Welcome to NEXUS, the autonomous gaming agent.")
        self.print("  This wizard will configure everything you need.\n")
        self.print("  [dim]You can change any setting later in ~/.nexus/config.yaml[/dim]\n")

    def step_game_selection(self):
        """Select which game to play."""
        self.print("[bold]Step 1: Game Selection[/bold]\n")

        try:
            from games.registry import list_games
            games = list_games()
            game_names = [g.name for g in games]
            game_ids = [g.id for g in games]

            if not games:
                self.print("  [yellow]No games registered. Using default: Tibia[/yellow]")
                self.config["game"] = "tibia"
                return

            selected_name = self.choose("Which game?", game_names, default="Tibia")
            idx = game_names.index(selected_name)
            self.config["game"] = game_ids[idx]

            # Get default config from the adapter
            from games.registry import get_adapter
            adapter = get_adapter(self.config["game"])
            if adapter:
                self.config["defaults"] = adapter.get_default_config()

        except ImportError:
            self.print("  [yellow]Game registry not available. Using default: Tibia[/yellow]")
            self.config["game"] = "tibia"

        self.print(f"\n  [green]✓[/green] Selected: [cyan]{self.config['game'].title()}[/cyan]\n")

    def step_character(self):
        """Configure character details."""
        self.print("[bold]Step 2: Character Configuration[/bold]\n")

        self.config["character_name"] = self.ask("Character name", "MyCharacter")
        self.config["server"] = self.ask("Server name", "MyServer")

        if self.config["game"] == "tibia":
            vocations = ["Elite Knight", "Royal Paladin", "Elder Druid", "Master Sorcerer"]
            self.config["vocation"] = self.choose("Vocation?", vocations, default="Elite Knight")

        self.print(f"\n  [green]✓[/green] Character: [cyan]{self.config['character_name']}[/cyan] "
                   f"on [cyan]{self.config['server']}[/cyan]\n")

    def step_api_key(self):
        """Configure Anthropic API key."""
        self.print("[bold]Step 3: AI Configuration[/bold]\n")

        self.print("  NEXUS uses Claude AI for strategic thinking.")
        self.print("  You need an Anthropic API key for the full experience.")
        self.print("  [dim]Get one at: https://console.anthropic.com/settings/keys[/dim]\n")

        existing_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if existing_key:
            masked = existing_key[:8] + "..." + existing_key[-4:]
            self.print(f"  [green]✓[/green] API key found in environment: {masked}")
            self.config["has_api_key"] = True
        else:
            key = self.ask("Anthropic API key (or press Enter to skip)", "")
            if key:
                self.config["api_key"] = key
                self.config["has_api_key"] = True
                self.print("\n  [green]✓[/green] API key configured")

                # Offer to save to shell profile
                if self.confirm("Save API key to shell profile (~/.zshrc or ~/.bashrc)?"):
                    self._save_api_key_to_profile(key)
            else:
                self.config["has_api_key"] = False
                self.print("\n  [yellow]![/yellow] Skipped. NEXUS will work without AI, "
                           "but strategic brain will be disabled.")
                self.print("  [dim]Set later: export ANTHROPIC_API_KEY=your_key[/dim]")

        self.print()

    def step_hotkeys(self):
        """Configure game hotkeys."""
        self.print("[bold]Step 4: Hotkey Configuration[/bold]\n")

        self.print("  Configure your in-game hotkey bindings.")
        self.print("  [dim]These must match your Tibia client hotkey settings.[/dim]\n")

        defaults = {
            "heal_critical": "F1",
            "heal_medium": "F2",
            "mana_potion": "F3",
            "haste": "F4",
            "attack_spell": "F5",
            "area_spell": "F6",
            "exeta_res": "F7",
            "ultimate_heal": "F8",
        }

        if self.confirm("Use default hotkeys (F1-F8)?", default=True):
            self.config["hotkeys"] = defaults
            self.print("\n  [green]✓[/green] Using defaults (F1-F8)")
        else:
            hotkeys = {}
            for action, default in defaults.items():
                label = action.replace("_", " ").title()
                hotkeys[action] = self.ask(f"{label}", default)
            self.config["hotkeys"] = hotkeys
            self.print("\n  [green]✓[/green] Custom hotkeys configured")

        self.print()

    def step_healing(self):
        """Configure healing thresholds."""
        self.print("[bold]Step 5: Healing Thresholds[/bold]\n")

        self.print("  When should NEXUS heal your character?")
        self.print("  [dim]NEXUS will auto-adjust these over time.[/dim]\n")

        if self.confirm("Use recommended thresholds? (Critical: 30%, Medium: 60%)", default=True):
            self.config["healing"] = {
                "critical_hp": 30,
                "medium_hp": 60,
                "mana_threshold": 50,
            }
        else:
            self.config["healing"] = {
                "critical_hp": self.ask_int("Critical heal at HP%", 30),
                "medium_hp": self.ask_int("Medium heal at HP%", 60),
                "mana_threshold": self.ask_int("Mana potion at mana%", 50),
            }

        self.print("\n  [green]✓[/green] Healing configured\n")

    def step_dashboard(self):
        """Configure dashboard."""
        self.print("[bold]Step 6: Dashboard[/bold]\n")

        self.config["dashboard_enabled"] = self.confirm(
            "Enable web dashboard? (Recommended)", default=True
        )

        if self.config["dashboard_enabled"]:
            self.config["dashboard_port"] = self.ask_int("Dashboard port", 8420)
            self.print(f"\n  [green]✓[/green] Dashboard at http://127.0.0.1:{self.config['dashboard_port']}")
        else:
            self.config["dashboard_port"] = 8420
            self.print("\n  [dim]Dashboard disabled[/dim]")

        self.print()

    def step_generate_config(self):
        """Generate the final config file."""
        self.print("[bold]Generating configuration...[/bold]\n")

        # Build full config
        base = self.config.get("defaults", {})

        full_config = {
            "agent": {
                "game": self.config.get("game", "tibia"),
                "character_name": self.config.get("character_name", "MyCharacter"),
                "server": self.config.get("server", "MyServer"),
            },
            "perception": base.get("perception", {
                "capture": {
                    "backend": "dxcam" if sys.platform == "win32" else "mss",
                    "fps": 30,
                    "monitor_index": 0,
                    "game_window_title": "Tibia",
                },
            }),
            "reactive": {
                "tick_rate_ms": 25,
                "healing": self.config.get("healing", {
                    "critical_hp": 30, "medium_hp": 60, "mana_threshold": 50,
                }),
                "hotkeys": self.config.get("hotkeys", {}),
            },
            "ai": base.get("ai", {
                "model_strategic": "claude-sonnet-4-20250514",
                "strategic_cycle_seconds": 3,
                "max_tokens": 1024,
                "temperature": 0.2,
                "api_key_env": "ANTHROPIC_API_KEY",
            }),
            "input": base.get("input", {
                "human_delay_min_ms": 30,
                "human_delay_max_ms": 80,
                "click_variance_px": 3,
            }),
            "skills": base.get("skills", {
                "directory": "skills/tibia",
                "auto_create": True,
                "auto_improve": True,
            }),
            "navigation": base.get("navigation", {}),
            "exploration": base.get("exploration", {}),
            "dashboard": {
                "enabled": self.config.get("dashboard_enabled", True),
                "host": "127.0.0.1",
                "port": self.config.get("dashboard_port", 8420),
            },
        }

        # Ensure directories exist
        NEXUS_HOME.mkdir(parents=True, exist_ok=True)
        (NEXUS_HOME / "data").mkdir(exist_ok=True)
        (NEXUS_HOME / "logs").mkdir(exist_ok=True)

        # Recursively convert tuples to lists (tuples serialize as
        # !!python/tuple which yaml.safe_load rejects)
        def _sanitize(obj):
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_sanitize(i) for i in obj]
            return obj

        full_config = _sanitize(full_config)

        # Write config (safe_dump avoids Python-specific YAML tags)
        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(full_config, f, default_flow_style=False, sort_keys=False)

        self.print(f"  [green]✓[/green] Config saved: [cyan]{CONFIG_PATH}[/cyan]\n")

    def step_summary(self):
        """Show setup summary."""
        self.print("[bold green]═══════════════════════════════════════════[/bold green]")
        self.print("[bold green]  Setup Complete![/bold green]")
        self.print("[bold green]═══════════════════════════════════════════[/bold green]\n")

        self.print(f"  Game:       [cyan]{self.config.get('game', 'tibia').title()}[/cyan]")
        self.print(f"  Character:  [cyan]{self.config.get('character_name', '?')}[/cyan]")
        self.print(f"  Server:     [cyan]{self.config.get('server', '?')}[/cyan]")
        self.print(f"  AI:         [cyan]{'Enabled' if self.config.get('has_api_key') else 'Disabled'}[/cyan]")
        self.print(f"  Dashboard:  [cyan]{'Enabled' if self.config.get('dashboard_enabled') else 'Disabled'}[/cyan]")
        self.print(f"  Config:     [cyan]{CONFIG_PATH}[/cyan]")

        self.print("\n  [bold]Next steps:[/bold]")
        self.print("    1. Open your game (Tibia)")
        self.print("    2. Run: [cyan]nexus start[/cyan]")
        self.print("    3. Open: [cyan]http://127.0.0.1:8420[/cyan]")
        self.print("")
        self.print("  [dim]Edit config anytime: ~/.nexus/config.yaml[/dim]")
        self.print("  [dim]Recalibrate: nexus calibrate[/dim]")
        self.print("")

    def _save_api_key_to_profile(self, key: str):
        """Save API key to shell profile."""
        export_line = f'\nexport ANTHROPIC_API_KEY="{key}"\n'

        # Determine shell profile
        shell = os.environ.get("SHELL", "/bin/bash")
        if "zsh" in shell:
            profile = Path.home() / ".zshrc"
        else:
            profile = Path.home() / ".bashrc"

        try:
            content = profile.read_text() if profile.exists() else ""
            if "ANTHROPIC_API_KEY" not in content:
                with open(profile, "a") as f:
                    f.write(f"\n# NEXUS API Key{export_line}")
                self.print(f"  [green]✓[/green] API key saved to {profile}")
            else:
                self.print(f"  [yellow]![/yellow] API key already in {profile}")
        except Exception as e:
            self.print(f"  [yellow]![/yellow] Could not write to {profile}: {e}")

    # ═══════════════════════════════════════════════════════
    #  Run
    # ═══════════════════════════════════════════════════════

    def run(self):
        """Run the full setup wizard."""
        self.step_welcome()
        self.step_game_selection()
        self.step_character()
        self.step_api_key()
        self.step_hotkeys()
        self.step_healing()
        self.step_dashboard()
        self.step_generate_config()
        self.step_summary()


def run_setup_wizard():
    """Entry point for the setup wizard."""
    wizard = SetupWizard()
    wizard.run()


if __name__ == "__main__":
    run_setup_wizard()
