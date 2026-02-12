#!/usr/bin/env python3
"""
NEXUS — Cross-Platform Launcher

Provides a simple way to start NEXUS with the dashboard.
On macOS: Opens terminal + browser
On Windows: Opens console + browser
On Linux: Opens terminal + browser

Can also be double-clicked from file manager on any platform.
"""

from __future__ import annotations

import os
import sys
import time
import subprocess
import webbrowser
import threading
from pathlib import Path

DASHBOARD_URL = "http://127.0.0.1:8420"
NEXUS_HOME = Path.home() / ".nexus"


def print_startup():
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
    ║     ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗  ║
    ║     ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝  ║
    ║     ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗  ║
    ║     ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║  ║
    ║     ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║  ║
    ║     ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝╚══════╝  ║
    ║                                                   ║
    ║         Autonomous Gaming Agent v0.1.0            ║
    ║                                                   ║
    ╚═══════════════════════════════════════════════════╝
    """)


def check_first_run() -> bool:
    """Check if this is the first time running NEXUS."""
    config = NEXUS_HOME / "config.yaml"
    return not config.exists()


def run_setup():
    """Run setup wizard if needed."""
    print("  First time running NEXUS? Let's set you up!\n")
    print("  Running setup wizard...\n")

    try:
        # Try to import and run the setup wizard
        setup_script = Path(__file__).parent / "scripts" / "setup_wizard.py"
        if setup_script.exists():
            subprocess.run([sys.executable, str(setup_script)], check=True)
        else:
            print("  Setup wizard not found. Creating minimal config...")
            NEXUS_HOME.mkdir(parents=True, exist_ok=True)

            # Use Tibia adapter for default config
            try:
                from games.tibia.adapter import TibiaAdapter
                adapter = TibiaAdapter()
                config = adapter.get_default_config()

                import yaml
                config_path = NEXUS_HOME / "config.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                print(f"  Config created: {config_path}")
            except ImportError:
                print("  Could not create config. Run: nexus setup")
                return False
    except Exception as e:
        print(f"  Setup error: {e}")
        return False

    return True


def open_dashboard_delayed():
    """Open the dashboard in the browser after a short delay."""
    time.sleep(3)  # Wait for server to start
    try:
        webbrowser.open(DASHBOARD_URL)
        print(f"\n  Dashboard opened: {DASHBOARD_URL}")
    except Exception:
        print(f"\n  Open in browser: {DASHBOARD_URL}")


def launch():
    """Main launcher entry point."""
    print_startup()

    # Check Python version
    if sys.version_info < (3, 11):
        print(f"  ERROR: Python 3.11+ required (you have {sys.version})")
        print("  Download from: https://python.org/downloads/")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    # First run setup
    if check_first_run():
        if not run_setup():
            input("\n  Press Enter to exit...")
            sys.exit(1)

    # Check dependencies
    missing = []
    for module, name in [("cv2", "opencv-python"), ("yaml", "pyyaml"),
                         ("structlog", "structlog"), ("aiohttp", "aiohttp"),
                         ("click", "click"), ("rich", "rich")]:
        try:
            __import__(module)
        except ImportError:
            missing.append(name)

    if missing:
        print(f"  Installing dependencies: {', '.join(missing)}")
        subprocess.run([
            sys.executable, "-m", "pip", "install", *missing,
            "--quiet", "--disable-pip-version-check",
        ])
        print("  Dependencies installed!\n")

    # Open dashboard in background
    dashboard_thread = threading.Thread(target=open_dashboard_delayed, daemon=True)
    dashboard_thread.start()

    print(f"  Starting NEXUS with dashboard...")
    print(f"  Dashboard will open at: {DASHBOARD_URL}")
    print(f"  Press Ctrl+C to stop.\n")

    # Run the agent
    try:
        subprocess.run([
            sys.executable, "-m", "nexus_cli", "start",
            "--dashboard", "--port", "8420",
        ])
    except KeyboardInterrupt:
        print("\n  Shutting down...")
    except FileNotFoundError:
        # Direct import fallback
        try:
            from nexus_cli import cli
            cli(["start", "--dashboard"])
        except Exception as e:
            print(f"  Error: {e}")

    input("\n  Press Enter to exit...")


if __name__ == "__main__":
    launch()
