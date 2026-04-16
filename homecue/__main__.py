"""CLI entry point for HomeCue. Run with: python -m homecue"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from homecue import __version__
from homecue.config import load_config
from homecue.core import HomeCueService


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

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

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

        service.run()


if __name__ == "__main__":
    main()
