"""System tray icon for running HomeCue in the background on Windows."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

import pystray

if TYPE_CHECKING:
    from homecue.core import HomeCueService

log = logging.getLogger(__name__)

# Tray icon size
_ICON_SIZE = 64


def _create_icon_image() -> Image.Image:
    """Generate a simple HomeCue tray icon programmatically."""
    img = Image.new("RGB", (_ICON_SIZE, _ICON_SIZE), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Draw "HC" text centered
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "HC", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (_ICON_SIZE - text_w) // 2
    y = (_ICON_SIZE - text_h) // 2
    draw.text((x, y), "HC", fill=(0, 200, 255), font=font)

    return img


def run_in_tray(service: HomeCueService) -> None:
    """Run HomeCueService in the background with a system tray icon."""

    def on_quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        log.info("Quit requested from tray")
        service.shutdown()
        icon.stop()

    def service_thread() -> None:
        try:
            service.run()
        except Exception:
            log.exception("Service error")
        # If service exits on its own, stop the tray icon too
        try:
            icon.stop()
        except Exception:
            pass

    from homecue import __version__

    menu = pystray.Menu(
        pystray.MenuItem(f"HomeCue v{__version__}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon(
        name="HomeCue",
        icon=_create_icon_image(),
        title="HomeCue - iCUE to Home Assistant Bridge",
        menu=menu,
    )

    # Run the service in a background thread
    thread = threading.Thread(target=service_thread, daemon=True, name="homecue-service")
    thread.start()

    # pystray.Icon.run() blocks (it runs the Windows message loop)
    log.info("HomeCue running in system tray")
    icon.run()
