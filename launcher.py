#!/usr/bin/env python3
"""
NEXUS — Cross-Platform Launcher

The simplest way to start NEXUS.
Can be double-clicked from file manager on any platform.

On Windows: Opens TUI dashboard in the terminal.
On macOS/Linux: Opens TUI in the current terminal.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

NEXUS_HOME = Path.home() / ".nexus"


def print_startup():
    print("""
    ╔═══════════════════════════════════════════╗
    ║                                           ║
    ║   ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗   ║
    ║   ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝   ║
    ║   ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗   ║
    ║   ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║   ║
    ║   ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║   ║
    ║   ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝   ║
    ║                                           ║
    ║        Autonomous Gaming Agent v0.4.2     ║
    ║                                           ║
    ╚═══════════════════════════════════════════╝
    """)


def check_python():
    """Ensure Python 3.10+."""
    if sys.version_info < (3, 10):
        print(f"  ERROR: Python 3.10+ required (you have {sys.version})")
        print("  Download from: https://python.org/downloads/")
        input("\n  Press Enter to exit...")
        sys.exit(1)


def check_dependencies():
    """Auto-install missing dependencies."""
    required = [
        ("cv2", "opencv-python"),
        ("yaml", "pyyaml"),
        ("structlog", "structlog"),
        ("click", "click"),
        ("rich", "rich"),
        ("textual", "textual"),
        ("numpy", "numpy"),
        ("pynput", "pynput"),
    ]

    missing = []
    for module, package in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"  Installing: {', '.join(missing)}")
        subprocess.run([
            sys.executable, "-m", "pip", "install", *missing,
            "--quiet", "--disable-pip-version-check",
        ])
        print("  Done!\n")


def check_config():
    """Create config from example if it doesn't exist."""
    repo_dir = Path(__file__).parent
    config_file = repo_dir / "config" / "settings.yaml"
    config_example = repo_dir / "config" / "settings.yaml.example"

    if not config_file.exists() and config_example.exists():
        import shutil
        shutil.copy(config_example, config_file)
        print(f"  Config created: {config_file}")
        print(f"  Edit it with your character name and hotkeys!\n")


def launch():
    """Main entry point."""
    print_startup()
    check_python()
    check_dependencies()
    check_config()

    print("  Starting NEXUS with TUI dashboard...")
    print("  Press Q to quit, P to pause.\n")

    try:
        # Try the installed CLI command first
        from nexus_cli import cli
        sys.argv = ["nexus", "start"]
        cli()
    except ImportError:
        # Fallback: run as module
        subprocess.run([sys.executable, "-m", "nexus_cli", "start"])
    except KeyboardInterrupt:
        print("\n  Shutting down...")
    except Exception as e:
        print(f"\n  Error: {e}")
        input("\n  Press Enter to exit...")


if __name__ == "__main__":
    launch()
