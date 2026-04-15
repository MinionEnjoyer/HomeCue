"""Main service orchestrator that wires all HomeCue components together."""

from __future__ import annotations

import logging
import threading
import time

from homecue.config import HomeCueConfig
from homecue.const import EFFECT_STATIC, PROFILE_NONE
from homecue.effects.engine import EffectsEngine
from homecue.icue.bridge import IcueBridge
from homecue.icue.devices import CorsairDevice
from homecue.icue.profiles import ProfileManager
from homecue.mqtt.client import MqttClient
from homecue.mqtt.discovery import HaDiscovery

log = logging.getLogger(__name__)


class HomeCueService:
    """Orchestrates the iCUE-to-Home-Assistant bridge."""

    def __init__(self, config: HomeCueConfig) -> None:
        self._config = config
        self._running = False
        self._devices: dict[str, CorsairDevice] = {}
        self._lock = threading.Lock()

        # iCUE bridge
        self._bridge = IcueBridge(
            exclusive=config.exclusive_access,
            on_devices_changed=self._on_devices_changed,
        )

        # MQTT client
        self._mqtt = MqttClient(
            host=config.mqtt.host,
            port=config.mqtt.port,
            username=config.mqtt.username,
            password=config.mqtt.password,
            client_id=config.mqtt.client_id,
        )

        # HA discovery
        self._discovery = HaDiscovery(
            mqtt_client=self._mqtt,
            discovery_prefix=config.mqtt.discovery_prefix,
        )

        # Effects engine
        self._effects = EffectsEngine(
            color_setter=self._bridge.set_device_color,
            fps=config.effects_fps,
        )

        # Profile manager (optional, requires profiles_path config)
        self._profiles: ProfileManager | None = None
        if config.profiles_path:
            self._profiles = ProfileManager(config.profiles_path)

    def run(self) -> None:
        """Start all components and run the main loop."""
        self._running = True

        # 1. Connect to iCUE
        if not self._bridge.connect():
            log.error("Could not connect to iCUE. Is iCUE running with SDK enabled?")
            return

        # 2. Connect to MQTT
        try:
            self._mqtt.connect()
        except Exception:
            log.exception("Could not connect to MQTT broker")
            self._bridge.disconnect()
            return

        # 3. Start effects engine
        self._effects.start()

        # 4. Discover devices and publish to HA
        self._discover_and_publish()

        # 5. Initialize profile switching (if configured)
        self._init_profiles()

        # 6. Main loop
        log.info("HomeCue is running. Press Ctrl+C to stop.")
        try:
            while self._running:
                self._publish_all_states()
                time.sleep(self._config.poll_interval)
        except KeyboardInterrupt:
            log.info("Interrupted")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Gracefully stop all components."""
        self._running = False
        log.info("Shutting down HomeCue...")

        self._effects.stop()

        # Deactivate profile and remove discovery
        if self._profiles and self._profiles.is_initialized:
            self._profiles.deactivate()
            self._discovery.remove_profile_select()

        # Remove HA discovery entries
        with self._lock:
            for device in self._devices.values():
                self._discovery.remove_discovery(device)

        self._mqtt.disconnect()
        self._bridge.disconnect()
        log.info("HomeCue stopped")

    def _discover_and_publish(self) -> None:
        """Discover Corsair devices and register them with HA."""
        discovered = self._bridge.discover_devices()

        with self._lock:
            # Apply user-configured name overrides
            for device in discovered:
                if device.model in self._config.device_names:
                    device.name = self._config.device_names[device.model]

            self._devices = {d.device_id: d for d in discovered}

        if not discovered:
            log.warning("No Corsair devices found. Check iCUE and device connections.")
            return

        log.info("Found %d device(s), publishing to Home Assistant", len(discovered))

        for device in discovered:
            # Publish HA discovery config
            self._discovery.publish_discovery(device)

            # Subscribe to commands for this device
            self._discovery.subscribe_commands(
                device,
                lambda topic, payload, dev=device: self._handle_command(dev, payload),
            )

            # Publish initial state
            self._discovery.publish_state(device)

            # Apply initial color via bridge
            r, g, b = device.effective_color
            self._bridge.set_device_color(device.device_id, r, g, b)

    def _handle_command(self, device: CorsairDevice, payload: dict | str) -> None:
        """Process an incoming command from Home Assistant."""
        if not isinstance(payload, dict):
            log.warning("Ignoring non-JSON command for %s: %s", device.name, payload)
            return

        log.debug("Command for %s: %s", device.name, payload)
        device.update_from_command(payload)

        if not device.is_on:
            self._effects.stop_effect(device.device_id)
            self._bridge.set_device_color(device.device_id, 0, 0, 0)
        else:
            self._effects.set_effect(
                device.device_id,
                device.effect,
                device.r,
                device.g,
                device.b,
                device.brightness,
            )

        # Publish updated state back to HA
        self._discovery.publish_state(device)

    def _init_profiles(self) -> None:
        """Initialize profile switching if configured."""
        if not self._profiles:
            return

        if not self._profiles.initialize():
            log.warning("Profile switching unavailable (CgSDK init failed)")
            self._profiles = None
            return

        profiles = self._profiles.available_profiles()
        if profiles:
            log.info("Available profiles: %s", ", ".join(profiles))
        else:
            log.info(
                "No .cueprofile files found in %s. "
                "Export profiles from iCUE to enable switching.",
                self._config.profiles_path,
            )

        self._discovery.publish_profile_select(profiles)
        self._discovery.publish_profile_state(self._profiles.active_profile)
        self._discovery.subscribe_profile_commands(self._handle_profile_command)

    def _handle_profile_command(self, topic: str, payload: dict | str) -> None:
        """Process a profile selection command from Home Assistant."""
        if not self._profiles:
            return

        profile_name = payload if isinstance(payload, str) else str(payload)
        log.info("Profile command: %s", profile_name)

        if profile_name == PROFILE_NONE:
            self._profiles.deactivate()
        else:
            self._profiles.activate(profile_name)

        self._discovery.publish_profile_state(self._profiles.active_profile)

    def _publish_all_states(self) -> None:
        """Periodically publish state for all devices."""
        with self._lock:
            devices = list(self._devices.values())

        for device in devices:
            self._discovery.publish_state(device)

        if self._profiles and self._profiles.is_initialized:
            self._discovery.publish_profile_state(self._profiles.active_profile)

    def _on_devices_changed(self) -> None:
        """Callback when iCUE reports device connect/disconnect."""
        log.info("Device change detected, re-discovering...")
        # Remove old discovery entries
        with self._lock:
            for device in self._devices.values():
                self._discovery.remove_discovery(device)

        self._discover_and_publish()
