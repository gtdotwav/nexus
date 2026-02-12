#!/usr/bin/env python3
"""
NEXUS — Command Line Interface

The main entry point for the NEXUS gaming agent.

Usage:
    nexus start                  Start the agent with default config
    nexus start --dashboard      Start with web dashboard
    nexus start --game tibia     Start for a specific game
    nexus stop                   Stop a running agent
    nexus status                 Show agent status
    nexus setup                  Run first-time setup wizard
    nexus calibrate              Calibrate game perception
    nexus skills list            List all loaded skills
    nexus skills create          Create a new skill interactively
    nexus games                  List supported games
    nexus dashboard              Open dashboard only (connect to running agent)
    nexus version                Show version info
"""

from __future__ import annotations

import asyncio
import os
import sys
import json
import signal
import time

import click
import structlog
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

VERSION = "0.3.1"
NEXUS_HOME = Path.home() / ".nexus"
PID_FILE = NEXUS_HOME / "nexus.pid"
CONFIG_FILE = NEXUS_HOME / "config.yaml"


def get_banner() -> str:
    return """[bold cyan]
    ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
    ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
    ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
    ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
    ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║
    ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝
[/bold cyan]
    [dim]Autonomous Gaming Agent v{version}[/dim]
    [dim]Dual-Brain AI · Self-Improving · Always Learning[/dim]
""".format(version=VERSION)


def setup_logging(debug: bool = False):
    """Configure structured logging."""
    level = 10 if debug else 20
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def ensure_home_dir():
    """Create NEXUS home directory if it doesn't exist."""
    NEXUS_HOME.mkdir(parents=True, exist_ok=True)
    (NEXUS_HOME / "data").mkdir(exist_ok=True)
    (NEXUS_HOME / "logs").mkdir(exist_ok=True)
    (NEXUS_HOME / "skills").mkdir(exist_ok=True)


def check_environment() -> list[str]:
    """Check for required dependencies and environment."""
    issues = []

    if sys.version_info < (3, 11):
        issues.append(f"Python 3.11+ required (current: {sys.version_info.major}.{sys.version_info.minor})")

    required = [
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("yaml", "pyyaml"),
        ("structlog", "structlog"),
        ("aiohttp", "aiohttp"),
    ]

    for module, package in required:
        try:
            __import__(module)
        except ImportError:
            issues.append(f"Missing: {package}")

    return issues


# ═══════════════════════════════════════════════════════
#  CLI Commands
# ═══════════════════════════════════════════════════════

@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.pass_context
def cli(ctx, version):
    """NEXUS — Autonomous Gaming Agent"""
    if version:
        console.print(f"[cyan]NEXUS[/cyan] v{VERSION}")
        return
    if ctx.invoked_subcommand is None:
        console.print(get_banner())
        console.print("  Run [cyan]nexus --help[/cyan] for available commands.\n")


@cli.command()
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--game", "-g", default="tibia", help="Game to play (default: tibia)")
@click.option("--dashboard/--no-dashboard", default=True, help="Enable web dashboard")
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
@click.option("--port", "-p", default=8420, help="Dashboard port")
def start(config, game, dashboard, debug, port):
    """Start the NEXUS agent."""
    ensure_home_dir()
    setup_logging(debug)

    console.print(get_banner())

    # Check environment
    issues = check_environment()
    if issues:
        console.print("[red]Environment issues found:[/red]")
        for issue in issues:
            console.print(f"  [red]✗[/red] {issue}")
        console.print("\n  Run [cyan]nexus setup[/cyan] to fix these issues.")
        sys.exit(1)

    console.print(f"  [green]✓[/green] Environment OK")
    console.print(f"  [green]✓[/green] Game: [cyan]{game}[/cyan]")

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("  [yellow]![/yellow] ANTHROPIC_API_KEY not set (strategic brain disabled)")

    # Determine config path
    if config is None:
        config = str(CONFIG_FILE) if CONFIG_FILE.exists() else "config/settings.yaml"

    if not Path(config).exists():
        console.print(f"\n  [yellow]No config found.[/yellow] Run [cyan]nexus setup[/cyan] first.")
        console.print(f"  Or create a config at: {config}")
        sys.exit(1)

    console.print(f"  [green]✓[/green] Config: {config}")

    if dashboard:
        console.print(f"  [green]✓[/green] Dashboard: [cyan]http://127.0.0.1:{port}[/cyan]")

    console.print()

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    try:
        asyncio.run(_run_agent(config, game, dashboard, port))
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


async def _run_agent(config_path: str, game: str, with_dashboard: bool, port: int):
    """Internal: Run the agent with all systems."""
    from core.agent import NexusAgent
    from dashboard.server import DashboardServer

    agent = NexusAgent(config_path=config_path)

    dashboard_server = None
    if with_dashboard:
        dashboard_server = DashboardServer(agent, port=port)
        await dashboard_server.start()

    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(_shutdown(agent, dashboard_server))

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: signal_handler())

    try:
        await agent.start()
    except asyncio.CancelledError:
        pass
    finally:
        await _shutdown(agent, dashboard_server)


async def _shutdown(agent, dashboard_server):
    """Graceful shutdown."""
    try:
        await agent.stop()
    except Exception as e:
        console.print(f"[red]Agent stop error: {e}[/red]")

    if dashboard_server:
        try:
            await dashboard_server.stop()
        except Exception as e:
            console.print(f"[red]Dashboard stop error: {e}[/red]")


@cli.command()
def stop():
    """Stop a running NEXUS agent."""
    if not PID_FILE.exists():
        console.print("[yellow]No running agent found.[/yellow]")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Sent stop signal to NEXUS (PID {pid})[/green]")
    except ProcessLookupError:
        console.print("[yellow]Agent process not found (stale PID file).[/yellow]")
        PID_FILE.unlink()
    except PermissionError:
        console.print("[red]Permission denied. Try with sudo.[/red]")


@cli.command()
def status():
    """Show NEXUS agent status."""
    console.print(get_banner())

    # Check if running
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)  # Check if process exists
            console.print(f"  [green]● RUNNING[/green] (PID {pid})")
        except ProcessLookupError:
            console.print(f"  [red]● STOPPED[/red] (stale PID)")
            PID_FILE.unlink()
    else:
        console.print(f"  [dim]● NOT RUNNING[/dim]")

    console.print()

    # Environment
    issues = check_environment()
    if issues:
        console.print("  [red]Environment Issues:[/red]")
        for i in issues:
            console.print(f"    [red]✗[/red] {i}")
    else:
        console.print("  [green]✓[/green] Environment OK")

    # API Key
    if os.environ.get("ANTHROPIC_API_KEY"):
        console.print("  [green]✓[/green] ANTHROPIC_API_KEY set")
    else:
        console.print("  [yellow]![/yellow] ANTHROPIC_API_KEY not set")

    # Config
    if CONFIG_FILE.exists():
        console.print(f"  [green]✓[/green] Config: {CONFIG_FILE}")
    else:
        console.print(f"  [dim]○[/dim] No config (run [cyan]nexus setup[/cyan])")

    # Data
    data_dir = NEXUS_HOME / "data"
    if data_dir.exists():
        map_file = data_dir / "maps" / "world_map.json"
        if map_file.exists():
            size_mb = map_file.stat().st_size / 1024 / 1024
            console.print(f"  [green]✓[/green] Spatial memory: {size_mb:.1f} MB")
        else:
            console.print(f"  [dim]○[/dim] No spatial memory yet")

    # Skills
    skills_dir = Path("skills")
    if skills_dir.exists():
        yaml_count = len(list(skills_dir.rglob("*.yaml")))
        console.print(f"  [green]✓[/green] Skills: {yaml_count} loaded")

    console.print()


@cli.command()
def setup():
    """Run the first-time setup wizard."""
    from scripts.setup_wizard import run_setup_wizard
    run_setup_wizard()


@cli.command()
@click.option("--config", "-c", default="config/settings.yaml")
def calibrate(config):
    """Run game perception calibration."""
    console.print(get_banner())
    console.print("[cyan]Starting calibration...[/cyan]\n")

    async def _calibrate():
        import yaml
        with open(config) as f:
            cfg = yaml.safe_load(f)

        from perception.screen_capture import ScreenCapture
        capture = ScreenCapture(cfg["perception"])
        await capture.initialize()

        found = await capture.find_game_window("Tibia")
        if found:
            console.print("[green]✓[/green] Game window found!")
            frame = await capture.capture()
            if frame is not None:
                import cv2
                out = NEXUS_HOME / "calibration_screenshot.png"
                cv2.imwrite(str(out), frame)
                console.print(f"[green]✓[/green] Screenshot saved: {out}")
                console.print(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}")
        else:
            console.print("[red]✗[/red] Game window not found. Is Tibia running?")

    asyncio.run(_calibrate())


@cli.group()
def skills():
    """Manage NEXUS skills."""
    pass


@skills.command("list")
def skills_list():
    """List all available skills."""
    skills_dir = Path("skills")
    if not skills_dir.exists():
        console.print("[yellow]No skills directory found.[/yellow]")
        return

    table = Table(title="NEXUS Skills", border_style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Game", style="cyan")
    table.add_column("Category")
    table.add_column("Score", justify="right")
    table.add_column("Waypoints", justify="right")
    table.add_column("Version")

    import yaml
    for path in sorted(skills_dir.rglob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            table.add_row(
                data.get("name", "?"),
                data.get("game", "?"),
                data.get("category", "?"),
                f"{data.get('performance_score', 50):.0f}",
                str(len(data.get("waypoints", []))),
                data.get("version", "1.0"),
            )
        except Exception:
            pass

    console.print(table)


@skills.command("create")
@click.option("--game", "-g", default="tibia", help="Game for the skill")
def skills_create(game):
    """Create a new skill interactively."""
    from games.registry import get_adapter

    adapter = get_adapter(game)
    if adapter:
        template = adapter.get_skill_template()
        out_path = Path("skills") / game / f"new_skill_{int(time.time())}.yaml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(template)
        console.print(f"[green]✓[/green] Skill template created: {out_path}")
        console.print(f"  Edit the file and fill in your hunting details.")
    else:
        console.print(f"[red]Game '{game}' not found.[/red]")


@cli.command()
def games():
    """List supported games."""
    from games.registry import list_games

    table = Table(title="Supported Games", border_style="cyan")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Genre")
    table.add_column("Perspective")
    table.add_column("Capabilities")
    table.add_column("Version")

    for info in list_games():
        caps = ", ".join(c.name.lower() for c in info.capabilities[:4])
        if len(info.capabilities) > 4:
            caps += f" +{len(info.capabilities) - 4}"
        table.add_row(
            info.id, info.name, info.genre,
            info.perspective, caps, info.version,
        )

    console.print(table)
    console.print("\n  [dim]To add a new game, implement GameAdapter in games/<name>/adapter.py[/dim]")


@cli.command("dashboard")
@click.option("--port", "-p", default=8420)
def dashboard_only(port):
    """Open the dashboard (connects to running agent)."""
    import webbrowser
    url = f"http://127.0.0.1:{port}"

    if PID_FILE.exists():
        console.print(f"[green]Opening dashboard:[/green] {url}")
        webbrowser.open(url)
    else:
        console.print("[yellow]No running agent detected.[/yellow]")
        console.print(f"Start one with: [cyan]nexus start[/cyan]")


@cli.command()
def version():
    """Show version information."""
    console.print(f"[cyan]NEXUS[/cyan] v{VERSION}")
    console.print(f"  Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    console.print(f"  Platform: {sys.platform}")
    console.print(f"  Home: {NEXUS_HOME}")


if __name__ == "__main__":
    cli()
