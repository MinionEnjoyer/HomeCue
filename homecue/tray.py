"""System tray icon for running HomeCue in the background on Windows."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

import pystray

if TYPE_CHECKING:
    from homecue.core import HomeCueService

log = logging.getLogger(__name__)

# Tray icon size
_ICON_SIZE = 64

# Retry delay when service fails to start (seconds)
_RETRY_DELAY = 15


def _create_icon_image(status: str = "normal") -> Image.Image:
    """Generate a simple HomeCue tray icon programmatically.

    status: "normal" (cyan), "error" (red), "connecting" (yellow)
    """
    colors = {"normal": (0, 200, 255), "error": (255, 60, 60), "connecting": (255, 200, 0)}
    text_color = colors.get(status, colors["normal"])

    img = Image.new("RGB", (_ICON_SIZE, _ICON_SIZE), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "HC", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (_ICON_SIZE - text_w) // 2
    y = (_ICON_SIZE - text_h) // 2
    draw.text((x, y), "HC", fill=text_color, font=font)

    return img


def _get_log_path() -> str:
    """Return the path to the log file."""
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "homecue.log")
    )


def run_in_tray(service: HomeCueService) -> None:
    """Run HomeCueService in the background with a system tray icon."""
    stop_event = threading.Event()

    def on_open_log(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        log_path = _get_log_path()
        try:
            if sys.platform == "win32":
                os.startfile(log_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", log_path])
            else:
                subprocess.Popen(["xdg-open", log_path])
        except Exception:
            log.warning("Could not open log file: %s", log_path)

    def on_quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        log.info("Quit requested from tray")
        stop_event.set()
        service.shutdown()
        icon.stop()

    def service_thread() -> None:
        while not stop_event.is_set():
            try:
                icon.icon = _create_icon_image("connecting")
                icon.title = "HomeCue - Connecting..."
                log.info("Starting HomeCue service...")
                service.run()
            except Exception:
                log.exception("Service error")

            # If we get here the service exited (connection failure or error)
            if stop_event.is_set():
                break

            # Show error state and retry
            icon.icon = _create_icon_image("error")
            icon.title = f"HomeCue - Retrying in {_RETRY_DELAY}s (see homecue.log)"
            log.info("Service stopped. Retrying in %ds...", _RETRY_DELAY)

            # Wait for retry delay, but check stop_event so we exit promptly
            for _ in range(_RETRY_DELAY):
                if stop_event.is_set():
                    return
                time.sleep(1)

            # Reset service state for retry
            service._running = False

    def on_icon_ready(icon: pystray.Icon) -> None:
        """Called once the tray icon is visible — start the service thread."""
        thread = threading.Thread(target=service_thread, daemon=True, name="homecue-service")
        thread.start()

    from homecue import __version__

    menu = pystray.Menu(
        pystray.MenuItem(f"HomeCue v{__version__}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Log", on_open_log),
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon(
        name="HomeCue",
        icon=_create_icon_image("connecting"),
        title="HomeCue - Starting...",
        menu=menu,
    )

    log.info("HomeCue running in system tray")
    icon.run(setup=on_icon_ready)
