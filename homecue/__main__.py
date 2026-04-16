"""CLI entry point for HomeCue. Run with: python -m homecue"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys

from homecue import __version__
from homecue.config import load_config
from homecue.core import HomeCueService

# Log file lives next to the config / working directory
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "homecue.log")


def _setup_logging(level_name: str, tray_mode: bool) -> None:
    """Configure logging with file handler (always) and console handler (if not tray)."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)

    # Always write to a log file so tray mode has output
    log_path = os.path.normpath(LOG_FILE)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Console handler only when not in tray mode
    if not tray_mode:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)


def _pause_console() -> None:
    """Keep the console window open so the user can read output before it closes."""
    if sys.platform == "win32":
        print("\nPress Enter to close this window...")
        try:
            input()
        except EOFError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="homecue",
        description="Bridge Corsair iCUE RGB lighting to Home Assistant via MQTT",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"HomeCue {__version__}",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Run minimized to the system tray (Windows)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    _setup_logging(config.log_level, tray_mode=args.tray)

    service = HomeCueService(config)

    if args.tray:
        from homecue.tray import run_in_tray

        run_in_tray(service)
    else:
        def handle_signal(signum: int, frame: object) -> None:
            logging.getLogger(__name__).info("Received signal %d, shutting down...", signum)
            service.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            service.run()
        except Exception:
            logging.getLogger(__name__).exception("Fatal error")
        finally:
            service.shutdown()
            # Keep the console window open so the user can see what happened
            _pause_console()


if __name__ == "__main__":
    main()
