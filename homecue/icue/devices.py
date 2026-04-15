"""Corsair device data model."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field

from homecue.const import DEFAULT_BRIGHTNESS, DEFAULT_COLOR, EFFECT_STATIC


@dataclass
class CorsairDevice:
    """Represents a single Corsair RGB device discovered via iCUE."""

    device_id: str
    name: str
    model: str
    device_type: str
    led_count: int
    led_ids: list[int] = field(default_factory=list)

    # Current lighting state
    is_on: bool = True
    brightness: int = DEFAULT_BRIGHTNESS
    r: int = DEFAULT_COLOR[0]
    g: int = DEFAULT_COLOR[1]
    b: int = DEFAULT_COLOR[2]
    effect: str = EFFECT_STATIC

    # Thread safety for state updates
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def unique_id(self) -> str:
        """Stable unique ID derived from device_id for MQTT topics."""
        short_hash = hashlib.sha256(self.device_id.encode()).hexdigest()[:8]
        return f"homecue_{short_hash}"

    @property
    def effective_color(self) -> tuple[int, int, int]:
        """RGB color scaled by brightness. Returns (0,0,0) when off."""
        if not self.is_on:
            return (0, 0, 0)
        scale = self.brightness / 255.0
        return (
            int(self.r * scale),
            int(self.g * scale),
            int(self.b * scale),
        )

    def update_from_command(self, payload: dict) -> None:
        """Apply an HA JSON command payload to this device's state."""
        with self._lock:
            if "state" in payload:
                self.is_on = payload["state"] == "ON"
            if "brightness" in payload:
                self.brightness = max(0, min(255, int(payload["brightness"])))
            if "color" in payload:
                color = payload["color"]
                self.r = max(0, min(255, int(color.get("r", self.r))))
                self.g = max(0, min(255, int(color.get("g", self.g))))
                self.b = max(0, min(255, int(color.get("b", self.b))))
            if "effect" in payload:
                self.effect = payload["effect"]

    def to_state_payload(self) -> dict:
        """Build HA JSON state payload for this device."""
        with self._lock:
            state = {
                "state": "ON" if self.is_on else "OFF",
                "brightness": self.brightness,
                "color_mode": "rgb",
                "color": {"r": self.r, "g": self.g, "b": self.b},
                "effect": self.effect,
            }
        return state
