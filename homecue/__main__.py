"""CLI entry point for HomeCue. Run with: python -m homecue"""

from __future__ import annotations

import os
import sys
import traceback

# Project root — one level up from homecue/ package directory
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Log file and default config live in the project root
_LOG_FILE = os.path.join(_PROJECT_ROOT, "homecue.log")
_DEFAULT_CONFIG = os.path.join(_PROJECT_ROOT, "config.yaml")


def _crash_log(message: str) -> None:
    """Write a crash message to the log file using basic I/O (no dependencies)."""
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message)
            f.write("\n")
    except Exception:
        pass
    # Also try stderr in case a console is attached
    try:
        sys.stderr.write(message + "\n")
    except Exception:
        pass


def _pause_console() -> None:
    """Keep the console window open so the user can read output before it closes."""
    if sys.platform == "win32":
        try:
            print("\nPress Enter to close this window...")
            input()
        except (EOFError, OSError):
            pass


def _setup_logging(level_name: str, tray_mode: bool, log_file: str = _LOG_FILE) -> None:
    """Configure logging with file handler (always) and console handler (if not tray)."""
    import logging

    level = getattr(logging, level_name.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
    )

    root = logging.getLogger()
    root.setLevel(level)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if not tray_mode:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)


def main() -> None:
    import argparse
    import logging
    import signal

    from homecue import __version__
    parser = argparse.ArgumentParser(
        prog="homecue",
        description="Bridge Corsair iCUE RGB lighting to Home Assistant via MQTT",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=_DEFAULT_CONFIG,
        help="Path to config file (default: config.yaml in project root)",
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
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--status-file", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Keep dependency-heavy Windows SDK imports after argument parsing so
    # `homecue --help` and `homecue --version` work on any platform.
    from homecue.config import load_config
    from homecue.core import HomeCueService

    config = load_config(args.config)
    log_file = os.path.join(os.path.dirname(os.path.abspath(args.config)), "homecue.log")
    _setup_logging(config.log_level, tray_mode=args.tray, log_file=log_file)

    service = HomeCueService(config, status_path=args.status_file)

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
            if not args.no_pause:
                _pause_console()


def _entry() -> None:
    """Outermost entry point — catches everything including import errors."""
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        _crash_log(f"FATAL CRASH:\n{tb}")
        _pause_console()
        sys.exit(1)


def _entry_tray() -> None:
    """Entry point for homecue-tray.exe (gui_scripts — no console window).

    gui_scripts uses pythonw.exe which sets stdout/stderr to None.
    Any print/warning before logging is configured would crash, so we
    redirect them to devnull immediately.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    # Inject --tray into argv so main() takes the tray path
    sys.argv = [sys.argv[0], "--tray"]
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        tb = traceback.format_exc()
        _crash_log(f"FATAL CRASH:\n{tb}")
        sys.exit(1)


if __name__ == "__main__":
    _entry()
