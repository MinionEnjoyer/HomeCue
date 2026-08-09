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
    2: "Mouse", 4: "Mousemat", 8: "Headset", 16: "Headset Stand",
    32: "Fan LED Controller", 64: "LED Controller", 128: "Memory",
    256: "Cooler", 512: "Motherboard", 1024: "GPU",
    2048: "Touchbar", 4096: "Game Controller",
}
_DEVICE_TYPE_MASKS = tuple(mask for mask in _DEVICE_TYPE_NAMES if mask)


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
        self._events_subscribed = False
        self._announced_device_ids: set[str] = set()
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
                "Connected to iCUE (server v%s, SDK v%s, host iCUE v%s)",
                details.server_version,
                details.client_version,
                details.server_host_version,
            )

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

        # Some iCUE 5 builds return an empty list for CDT_All even though
        # category-specific filters expose devices. Try the efficient all-device
        # query first, then fall back to each SDK device category.
        device_filter = CorsairDeviceFilter(device_type_mask=CorsairDeviceType.CDT_All)
        devices_raw, err = self._sdk.get_devices(device_filter)
        if err != CorsairError.CE_Success:
            log.error("Device enumeration failed: %s", err)
            return []

        if not devices_raw:
            by_id = {}
            log.info("All-device SDK query returned no results; trying category filters")
            for mask in _DEVICE_TYPE_MASKS:
                category_devices, category_err = self._sdk.get_devices(
                    CorsairDeviceFilter(device_type_mask=mask)
                )
                if category_err != CorsairError.CE_Success:
                    log.warning(
                        "iCUE %s query failed: %s",
                        _DEVICE_TYPE_NAMES[mask],
                        category_err,
                    )
                    continue
                if category_devices:
                    log.info(
                        "iCUE reported %d %s device(s)",
                        len(category_devices),
                        _DEVICE_TYPE_NAMES[mask],
                    )
                    by_id.update({device.device_id: device for device in category_devices})
            devices_raw = list(by_id.values())
            if not devices_raw:
                log.warning("iCUE returned zero devices for every supported SDK category")

        if not devices_raw and self._announced_device_ids:
            log.info(
                "Trying %d device ID(s) announced by iCUE events",
                len(self._announced_device_ids),
            )
            announced = []
            for device_id in tuple(self._announced_device_ids):
                info, info_err = self._sdk.get_device_info(device_id)
                if info_err == CorsairError.CE_Success and info:
                    announced.append(info)
                else:
                    log.warning("Announced iCUE device %s is unavailable: %s", device_id, info_err)
            devices_raw = announced
        elif not devices_raw:
            log.warning("iCUE has not announced any device IDs to the SDK client")

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

    def set_led_color(self, device_id: str, led_id: int, r: int, g: int, b: int) -> bool:
        """Set one LED without changing the rest of the device."""
        with self._lock:
            device = self._devices.get(device_id)
        if not device or led_id not in device.led_ids:
            return False
        err = self._sdk.set_led_colors(device_id, [CorsairLedColor(led_id, r, g, b, 255)])
        if err != CorsairError.CE_Success:
            log.error("Failed to set LED %d on %s: %s", led_id, device.name, err)
            return False
        return True

    def _on_session_state_changed(self, event: object) -> None:
        """Callback for iCUE connection state changes."""
        state = event.state
        log.debug("iCUE session state: %s", state)

        if state == CorsairSessionState.CSS_Connected:
            # Subscribe inside the Connected callback. Corsair announces all
            # currently connected devices immediately after this transition,
            # so subscribing later can miss the initial device-ID events.
            if not self._events_subscribed:
                err = self._sdk.subscribe_for_events(self._on_device_event)
                if err == CorsairError.CE_Success:
                    self._events_subscribed = True
                    log.info("Subscribed to iCUE device events")
                else:
                    log.warning("Could not subscribe to device events: %s", err)
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
        data = getattr(event, "data", None)
        device_id = getattr(data, "device_id", None)
        is_connected = getattr(data, "is_connected", None)
        if device_id and is_connected is True:
            self._announced_device_ids.add(device_id)
        elif device_id and is_connected is False:
            self._announced_device_ids.discard(device_id)
        # Initial events arrive before Core finishes MQTT startup; the normal
        # initial discovery consumes the cached IDs. Notify Core for hotplug
        # changes only after it already has an inventory.
        if self._on_devices_changed and self._devices:
            self._on_devices_changed()
