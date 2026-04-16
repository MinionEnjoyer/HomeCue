"""iCUE SDK wrapper for device discovery and LED control."""

from __future__ import annotations

import logging
import threading
from typing import Callable

from cuesdk import (
    CorsairAccessLevel,
    CorsairDeviceFilter,
    CorsairDeviceType,
    CorsairError,
    CorsairLedColor,
    CorsairSessionState,
    CueSdk,
)

from homecue.icue.devices import CorsairDevice

log = logging.getLogger(__name__)

# Map SDK device type ints to human-readable strings
_DEVICE_TYPE_NAMES = {
    0: "Unknown",
    1: "Keyboard",
    2: "Mouse",
    3: "Mousemat",
    4: "Headset",
    5: "Headset Stand",
    6: "Fan LED Controller",
    7: "LED Controller",
    8: "Memory",
    9: "Cooler",
    10: "Motherboard",
    11: "GPU",
    12: "Touchbar",
    13: "Game Controller",
}


class IcueBridge:
    """Manages connection to iCUE and provides device discovery and LED control."""

    def __init__(
        self,
        exclusive: bool = False,
        on_devices_changed: Callable[[], None] | None = None,
    ) -> None:
        self._sdk = CueSdk()
        self._exclusive = exclusive
        self._on_devices_changed = on_devices_changed
        self._connected = threading.Event()
        self._devices: dict[str, CorsairDevice] = {}
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def connect(self, timeout: float = 10.0) -> bool:
        """Connect to the iCUE SDK. Returns True on success."""
        log.info("Connecting to iCUE...")
        self._connected.clear()

        err = self._sdk.connect(self._on_session_state_changed)
        if err != CorsairError.CE_Success:
            log.error("Failed to initiate iCUE connection: %s", err)
            return False

        if not self._connected.wait(timeout=timeout):
            log.error("Timed out waiting for iCUE connection (%.0fs)", timeout)
            return False

        details, err = self._sdk.get_session_details()
        if err == CorsairError.CE_Success:
            log.info(
                "Connected to iCUE (server v%s, SDK v%s)",
                details.server_version,
                details.client_version,
            )

        # Subscribe for hotplug events
        err = self._sdk.subscribe_for_events(self._on_device_event)
        if err != CorsairError.CE_Success:
            log.warning("Could not subscribe to device events: %s", err)

        return True

    def disconnect(self) -> None:
        """Release control and disconnect from iCUE."""
        if self._exclusive:
            for device_id in list(self._devices.keys()):
                self._sdk.release_control(device_id)
        self._connected.clear()
        log.info("Disconnected from iCUE")

    def discover_devices(self) -> list[CorsairDevice]:
        """Enumerate all Corsair devices visible to iCUE."""
        if not self.is_connected:
            log.warning("Cannot discover devices: not connected to iCUE")
            return []

        # Pass all device types to get every connected device
        all_types = 0
        for dt in CorsairDeviceType:
            all_types |= dt.value
        device_filter = CorsairDeviceFilter(device_type_mask=all_types)
        devices_raw, err = self._sdk.get_devices(device_filter)
        if err != CorsairError.CE_Success:
            log.error("Device enumeration failed: %s", err)
            return []

        discovered = []
        for dev in devices_raw:
            info, err = self._sdk.get_device_info(dev.device_id)
            if err != CorsairError.CE_Success:
                log.warning("Could not get info for device %s: %s", dev.device_id, err)
                continue

            # Get LED positions to know LED count and IDs
            leds, err = self._sdk.get_led_positions(dev.device_id)
            if err != CorsairError.CE_Success:
                log.warning("Could not get LEDs for %s: %s", info.model, err)
                leds = []

            led_ids = [led.id for led in leds] if leds else []
            device_type_name = _DEVICE_TYPE_NAMES.get(info.type, f"Type({info.type})")

            device = CorsairDevice(
                device_id=dev.device_id,
                name=info.model or f"Corsair {device_type_name}",
                model=info.model or "Unknown",
                device_type=device_type_name,
                led_count=len(led_ids),
                led_ids=led_ids,
            )

            if self._exclusive:
                ctrl_err = self._sdk.request_control(
                    dev.device_id,
                    CorsairAccessLevel.CAL_ExclusiveLightingControl,
                )
                if ctrl_err != CorsairError.CE_Success:
                    log.warning(
                        "Could not get exclusive control of %s: %s",
                        device.name,
                        ctrl_err,
                    )

            discovered.append(device)
            log.info(
                "Discovered: %s (%s) - %d LEDs",
                device.name,
                device.device_type,
                device.led_count,
            )

        with self._lock:
            self._devices = {d.device_id: d for d in discovered}

        return discovered

    def set_device_color(self, device_id: str, r: int, g: int, b: int) -> bool:
        """Set all LEDs on a device to a single color."""
        with self._lock:
            device = self._devices.get(device_id)

        if not device or not device.led_ids:
            return False

        colors = [CorsairLedColor(led_id, r, g, b, 255) for led_id in device.led_ids]
        err = self._sdk.set_led_colors(device_id, colors)
        if err != CorsairError.CE_Success:
            log.error("Failed to set colors on %s: %s", device.name, err)
            return False

        return True

    def _on_session_state_changed(self, event: object) -> None:
        """Callback for iCUE connection state changes."""
        state = event.state
        log.debug("iCUE session state: %s", state)

        if state == CorsairSessionState.CSS_Connected:
            log.info("iCUE session connected")
            self._connected.set()
        elif state == CorsairSessionState.CSS_ConnectionLost:
            log.warning("iCUE connection lost, will auto-reconnect")
            self._connected.clear()
        elif state == CorsairSessionState.CSS_Timeout:
            log.warning("iCUE connection timeout, retrying...")
            self._connected.clear()
        elif state == CorsairSessionState.CSS_ConnectionRefused:
            log.error(
                "iCUE refused connection. "
                "Ensure SDK is enabled: iCUE Settings > General > Enable SDK"
            )
            self._connected.clear()

    def _on_device_event(self, event: object) -> None:
        """Callback for device connect/disconnect events."""
        log.info("Device event: %s", event)
        if self._on_devices_changed:
            self._on_devices_changed()
