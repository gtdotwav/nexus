#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║                     N E X U S                             ║
║           Autonomous Gaming Agent v0.1.0                  ║
║                                                           ║
║  An AI agent that plays, learns, and evolves.             ║
║  Currently supporting: Tibia                              ║
╚═══════════════════════════════════════════════════════════╝

Usage:
    python main.py                    # Run with default config
    python main.py --config path.yaml # Run with custom config
    python main.py --calibrate        # Run calibration only
    python main.py --dashboard        # Run with web dashboard
"""

import asyncio
import argparse
import os
import sys
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
)

log = structlog.get_logger()


def print_banner():
    banner = """
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
    ║         Dual-Brain Architecture | Self-Improving  ║
    ║                                                   ║
    ╚═══════════════════════════════════════════════════╝
    """
    print(banner)


def check_environment():
    """Verify all required environment variables and dependencies."""
    issues = []

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        issues.append("ANTHROPIC_API_KEY environment variable not set")

    # Check Python version
    if sys.version_info < (3, 11):
        issues.append(f"Python 3.11+ required, got {sys.version_info.major}.{sys.version_info.minor}")

    # Check critical dependencies
    required_packages = [
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("yaml", "pyyaml"),
        ("pydantic", "pydantic"),
        ("structlog", "structlog"),
    ]

    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
        except ImportError:
            issues.append(f"Missing package: {package_name} (pip install {package_name})")

    # Optional but recommended
    optional_packages = [
        ("anthropic", "anthropic"),
        ("pynput", "pynput"),
        ("easyocr", "easyocr"),
    ]

    for module_name, package_name in optional_packages:
        try:
            __import__(module_name)
        except ImportError:
            log.warning("dependency.optional_missing", package=package_name)

    if issues:
        for issue in issues:
            log.error("environment.issue", detail=issue)
        return False

    return True


async def run_agent(config_path: str, with_dashboard: bool = False):
    """Main entry point to start the NEXUS agent."""
    from core.agent import NexusAgent

    agent = NexusAgent(config_path=config_path)

    if with_dashboard:
        log.info("dashboard.starting", url="http://127.0.0.1:8420")
        # TODO: Start FastAPI dashboard in separate task

    await agent.start()


async def run_calibration(config_path: str):
    """Run perception calibration only."""
    from perception.screen_capture import ScreenCapture
    import yaml

    with open(config_path) as f:
        config = yaml.safe_load(f)

    capture = ScreenCapture(config["perception"])
    await capture.initialize()

    # Find game window
    found = await capture.find_game_window("Tibia")
    if found:
        log.info("calibration.window_found")

        # Capture a test frame
        frame = await capture.capture()
        if frame is not None:
            import cv2
            cv2.imwrite("calibration_screenshot.png", frame)
            log.info("calibration.screenshot_saved", file="calibration_screenshot.png")
            log.info("calibration.frame_size", width=frame.shape[1], height=frame.shape[0])
    else:
        log.error("calibration.window_not_found", hint="Make sure Tibia is open")


def main():
    parser = argparse.ArgumentParser(description="NEXUS - Autonomous Gaming Agent")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to config file")
    parser.add_argument("--calibrate", action="store_true", help="Run calibration only")
    parser.add_argument("--dashboard", action="store_true", help="Enable web dashboard")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(10),  # DEBUG level
        )

    print_banner()

    if not check_environment():
        log.error("startup.failed", reason="Environment check failed")
        sys.exit(1)

    log.info("startup.environment_ok")

    if args.calibrate:
        asyncio.run(run_calibration(args.config))
    else:
        asyncio.run(run_agent(args.config, with_dashboard=args.dashboard))


if __name__ == "__main__":
    main()
