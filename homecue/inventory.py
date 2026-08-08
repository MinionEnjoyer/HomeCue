"""Small JSON snapshot shared by the service and desktop control center."""

from __future__ import annotations

import json
import os
from pathlib import Path

from homecue.icue.devices import CorsairDevice


class InventoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, devices: list[CorsairDevice], connected: bool) -> None:
        payload = {
            "connected": connected,
            "count": len(devices),
            "devices": [
                {
                    "id": device.unique_id,
                    "name": device.name,
                    "model": device.model,
                    "type": device.device_type,
                    "ledCount": device.led_count,
                    "capabilities": ["lighting", "brightness", "effects"]
                    + (["individual-leds"] if device.led_ids else []),
                }
                for device in devices
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
