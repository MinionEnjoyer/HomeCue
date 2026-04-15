"""Background effects engine for animated lighting."""

from __future__ import annotations

import colorsys
import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

from homecue.const import (
    DEFAULT_EFFECTS_FPS,
    EFFECT_BREATHING,
    EFFECT_COLOR_CYCLE,
    EFFECT_RAINBOW,
    EFFECT_STATIC,
)

log = logging.getLogger(__name__)

# Color cycle palette
_CYCLE_COLORS = [
    (255, 0, 0),
    (255, 165, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 0, 255),
    (128, 0, 255),
]


@dataclass
class _ActiveEffect:
    """Tracks an active effect on a device."""

    effect_name: str
    base_r: int
    base_g: int
    base_b: int
    brightness: int
    started_at: float


class EffectsEngine:
    """Runs animated lighting effects in a background thread.

    This engine is decoupled from the iCUE SDK. It calls a provided
    color_setter callback to apply colors, which the caller wires to
    the iCUE bridge.
    """

    def __init__(
        self,
        color_setter: Callable[[str, int, int, int], None],
        fps: int = DEFAULT_EFFECTS_FPS,
    ) -> None:
        self._color_setter = color_setter
        self._fps = fps
        self._interval = 1.0 / fps

        self._effects: dict[str, _ActiveEffect] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the effects animation thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="effects")
        self._thread.start()
        log.info("Effects engine started (%d FPS)", self._fps)

    def stop(self) -> None:
        """Stop the effects animation thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        log.info("Effects engine stopped")

    def set_effect(
        self,
        device_id: str,
        effect_name: str,
        r: int = 255,
        g: int = 255,
        b: int = 255,
        brightness: int = 255,
    ) -> None:
        """Set or change the active effect on a device."""
        with self._lock:
            if effect_name == EFFECT_STATIC:
                # Static just sets the color once and removes from animation
                self._effects.pop(device_id, None)
                scale = brightness / 255.0
                self._color_setter(
                    device_id,
                    int(r * scale),
                    int(g * scale),
                    int(b * scale),
                )
                return

            self._effects[device_id] = _ActiveEffect(
                effect_name=effect_name,
                base_r=r,
                base_g=g,
                base_b=b,
                brightness=brightness,
                started_at=time.monotonic(),
            )

    def stop_effect(self, device_id: str) -> None:
        """Stop any active effect on a device and set it to black."""
        with self._lock:
            self._effects.pop(device_id, None)
        self._color_setter(device_id, 0, 0, 0)

    def has_active_effect(self, device_id: str) -> bool:
        """Check if a device has a running animated effect."""
        with self._lock:
            return device_id in self._effects

    def _run_loop(self) -> None:
        """Main animation loop running at target FPS."""
        while self._running:
            tick_start = time.monotonic()

            with self._lock:
                effects_snapshot = dict(self._effects)

            now = time.monotonic()
            for device_id, effect in effects_snapshot.items():
                elapsed = now - effect.started_at
                r, g, b = self._compute_color(effect, elapsed)
                try:
                    self._color_setter(device_id, r, g, b)
                except Exception:
                    log.exception("Error setting color for effect on %s", device_id)

            elapsed = time.monotonic() - tick_start
            sleep_time = self._interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _compute_color(
        self, effect: _ActiveEffect, elapsed: float
    ) -> tuple[int, int, int]:
        """Calculate the current RGB color for an effect at the given time."""
        scale = effect.brightness / 255.0

        if effect.effect_name == EFFECT_BREATHING:
            # Sinusoidal breathing over a 4-second cycle
            cycle = 4.0
            intensity = (math.sin(2 * math.pi * elapsed / cycle - math.pi / 2) + 1) / 2
            return (
                int(effect.base_r * scale * intensity),
                int(effect.base_g * scale * intensity),
                int(effect.base_b * scale * intensity),
            )

        if effect.effect_name == EFFECT_RAINBOW:
            # HSV hue rotation over a 5-second cycle
            cycle = 5.0
            hue = (elapsed % cycle) / cycle
            r_f, g_f, b_f = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            return (
                int(r_f * 255 * scale),
                int(g_f * 255 * scale),
                int(b_f * 255 * scale),
            )

        if effect.effect_name == EFFECT_COLOR_CYCLE:
            # Step through preset colors, 2 seconds each
            step_duration = 2.0
            index = int(elapsed / step_duration) % len(_CYCLE_COLORS)
            cr, cg, cb = _CYCLE_COLORS[index]
            return (
                int(cr * scale),
                int(cg * scale),
                int(cb * scale),
            )

        # Fallback: static base color
        return (
            int(effect.base_r * scale),
            int(effect.base_g * scale),
            int(effect.base_b * scale),
        )
