"""Home Assistant MQTT auto-discovery for Corsair devices."""

from __future__ import annotations

import logging
from typing import Callable

from homecue import __version__
from homecue.const import (
    AVAILABILITY_TOPIC,
    COMMAND_TOPIC_TEMPLATE,
    DISCOVERY_TOPIC_TEMPLATE,
    EFFECTS_LIST,
    PAYLOAD_OFFLINE,
    PAYLOAD_ONLINE,
    STATE_TOPIC_TEMPLATE,
)
from homecue.icue.devices import CorsairDevice
from homecue.mqtt.client import MqttClient

log = logging.getLogger(__name__)


class HaDiscovery:
    """Publishes and manages Home Assistant MQTT discovery for Corsair devices."""

    def __init__(self, mqtt_client: MqttClient, discovery_prefix: str = "homeassistant") -> None:
        self._mqtt = mqtt_client
        self._discovery_prefix = discovery_prefix

    def publish_discovery(self, device: CorsairDevice) -> None:
        """Publish an MQTT discovery config so HA creates a light entity."""
        unique_id = device.unique_id
        discovery_topic = self._discovery_topic(unique_id)

        payload = {
            "name": device.name,
            "unique_id": unique_id,
            "schema": "json",
            "command_topic": COMMAND_TOPIC_TEMPLATE.format(unique_id=unique_id),
            "state_topic": STATE_TOPIC_TEMPLATE.format(unique_id=unique_id),
            "availability": {
                "topic": AVAILABILITY_TOPIC,
                "payload_available": PAYLOAD_ONLINE,
                "payload_not_available": PAYLOAD_OFFLINE,
            },
            "supported_color_modes": ["rgb"],
            "brightness": True,
            "brightness_scale": 255,
            "effect": True,
            "effect_list": EFFECTS_LIST,
            "device": {
                "identifiers": [unique_id],
                "name": device.name,
                "manufacturer": "Corsair",
                "model": f"{device.device_type} ({device.led_count} LEDs)",
                "sw_version": __version__,
                "via_device": "homecue",
            },
        }

        self._mqtt.publish(discovery_topic, payload, retain=True, qos=1)
        log.info("Published HA discovery for %s (%s)", device.name, unique_id)

    def remove_discovery(self, device: CorsairDevice) -> None:
        """Remove a device from HA by publishing an empty discovery payload."""
        discovery_topic = self._discovery_topic(device.unique_id)
        self._mqtt.publish(discovery_topic, "", retain=True, qos=1)
        log.info("Removed HA discovery for %s", device.name)

    def publish_state(self, device: CorsairDevice) -> None:
        """Publish the current state of a device to HA."""
        state_topic = STATE_TOPIC_TEMPLATE.format(unique_id=device.unique_id)
        self._mqtt.publish(state_topic, device.to_state_payload(), retain=True)

    def subscribe_commands(
        self,
        device: CorsairDevice,
        callback: Callable[[str, dict | str], None],
    ) -> None:
        """Subscribe to HA command topic for a device."""
        command_topic = COMMAND_TOPIC_TEMPLATE.format(unique_id=device.unique_id)
        self._mqtt.subscribe(command_topic, callback)
        log.debug("Subscribed to commands for %s", device.name)

    def _discovery_topic(self, unique_id: str) -> str:
        return f"{self._discovery_prefix}/light/{unique_id}/config"
