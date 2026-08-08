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
    INVENTORY_DISCOVERY_TOPIC_TEMPLATE,
    INVENTORY_STATE_TOPIC,
    LED_COMMAND_TOPIC_TEMPLATE,
    LED_STATE_TOPIC_TEMPLATE,
    PAYLOAD_OFFLINE,
    PAYLOAD_ONLINE,
    PROFILE_COMMAND_TOPIC,
    PROFILE_DISCOVERY_TOPIC_TEMPLATE,
    PROFILE_NONE,
    PROFILE_SELECT_UNIQUE_ID,
    PROFILE_STATE_TOPIC,
    STATE_TOPIC_TEMPLATE,
    SYNC_DISCOVERY_TOPIC_TEMPLATE,
    SYNC_STATE_TOPIC_TEMPLATE,
)
from homecue.icue.devices import CorsairDevice
from homecue.mqtt.client import MqttClient

log = logging.getLogger(__name__)


class HaDiscovery:
    """Publishes and manages Home Assistant MQTT discovery for Corsair devices."""

    def __init__(self, mqtt_client: MqttClient, discovery_prefix: str = "homeassistant", suggested_area: str = "HomeCue") -> None:
        self._mqtt = mqtt_client
        self._discovery_prefix = discovery_prefix
        self._suggested_area = suggested_area

    def _device_info(self, device: CorsairDevice) -> dict:
        return {
            "identifiers": [device.unique_id],
            "name": device.name,
            "manufacturer": "Corsair",
            "model": f"{device.model} · {device.device_type}",
            "sw_version": __version__,
            "via_device": "homecue_service",
            "suggested_area": self._suggested_area,
        }

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
            "device": self._device_info(device),
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

    def publish_led_discovery(self, device: CorsairDevice, led_id: int) -> None:
        """Expose one physical LED as an independent HA light entity."""
        entity_id = f"{device.unique_id}_led_{led_id}"
        topic = f"{self._discovery_prefix}/light/{entity_id}/config"
        payload = {
            "name": f"LED {led_id}", "unique_id": entity_id, "schema": "json",
            "command_topic": LED_COMMAND_TOPIC_TEMPLATE.format(unique_id=device.unique_id, led_id=led_id),
            "state_topic": LED_STATE_TOPIC_TEMPLATE.format(unique_id=device.unique_id, led_id=led_id),
            "availability": {"topic": AVAILABILITY_TOPIC, "payload_available": PAYLOAD_ONLINE, "payload_not_available": PAYLOAD_OFFLINE},
            "supported_color_modes": ["rgb"], "brightness": True, "brightness_scale": 255,
            "device": self._device_info(device),
        }
        self._mqtt.publish(topic, payload, retain=True, qos=1)

    def publish_led_state(self, device: CorsairDevice, led_id: int, payload: dict) -> None:
        self._mqtt.publish(LED_STATE_TOPIC_TEMPLATE.format(unique_id=device.unique_id, led_id=led_id), payload, retain=True)

    def subscribe_led_commands(self, device: CorsairDevice, led_id: int, callback: Callable[[str, dict | str], None]) -> None:
        self._mqtt.subscribe(LED_COMMAND_TOPIC_TEMPLATE.format(unique_id=device.unique_id, led_id=led_id), callback)

    def remove_led_discovery(self, device: CorsairDevice, led_id: int) -> None:
        entity_id = f"{device.unique_id}_led_{led_id}"
        self._mqtt.publish(f"{self._discovery_prefix}/light/{entity_id}/config", "", retain=True, qos=1)

    def publish_inventory(self, devices: list[CorsairDevice]) -> None:
        """Publish a single HomeCue hub entity with inventory diagnostics."""
        topic = INVENTORY_DISCOVERY_TOPIC_TEMPLATE.replace("homeassistant", self._discovery_prefix, 1)
        payload = {
            "name": "Connected devices", "unique_id": "homecue_inventory",
            "state_topic": INVENTORY_STATE_TOPIC, "value_template": "{{ value_json.count }}",
            "json_attributes_topic": INVENTORY_STATE_TOPIC,
            "availability": {"topic": AVAILABILITY_TOPIC, "payload_available": PAYLOAD_ONLINE, "payload_not_available": PAYLOAD_OFFLINE},
            "device": {"identifiers": ["homecue_service"], "name": "HomeCue", "manufacturer": "HomeCue", "model": "iCUE Bridge", "sw_version": __version__, "suggested_area": self._suggested_area},
        }
        self._mqtt.publish(topic, payload, retain=True, qos=1)
        self._mqtt.publish(INVENTORY_STATE_TOPIC, {"count": len(devices), "devices": [{"id": d.unique_id, "name": d.name, "model": d.model, "type": d.device_type, "led_count": d.led_count} for d in devices]}, retain=True)

    def publish_profile_select(self, profiles: list[str]) -> None:
        """Publish an MQTT discovery config so HA creates a select entity for profiles."""
        unique_id = PROFILE_SELECT_UNIQUE_ID
        discovery_topic = PROFILE_DISCOVERY_TOPIC_TEMPLATE.format(unique_id=unique_id)
        discovery_topic = discovery_topic.replace(
            "homeassistant", self._discovery_prefix, 1
        )

        options = [PROFILE_NONE] + profiles

        payload = {
            "name": "iCUE Profile",
            "unique_id": unique_id,
            "command_topic": PROFILE_COMMAND_TOPIC,
            "state_topic": PROFILE_STATE_TOPIC,
            "options": options,
            "availability": {
                "topic": AVAILABILITY_TOPIC,
                "payload_available": PAYLOAD_ONLINE,
                "payload_not_available": PAYLOAD_OFFLINE,
            },
            "device": {
                "identifiers": ["homecue_service"],
                "name": "HomeCue",
                "manufacturer": "HomeCue",
                "model": "iCUE Bridge",
                "sw_version": __version__,
                "suggested_area": self._suggested_area,
            },
        }

        self._mqtt.publish(discovery_topic, payload, retain=True, qos=1)
        log.info("Published HA discovery for profile select (%d profiles)", len(profiles))

    def remove_profile_select(self) -> None:
        """Remove the profile select entity from HA."""
        unique_id = PROFILE_SELECT_UNIQUE_ID
        discovery_topic = PROFILE_DISCOVERY_TOPIC_TEMPLATE.format(unique_id=unique_id)
        discovery_topic = discovery_topic.replace(
            "homeassistant", self._discovery_prefix, 1
        )
        self._mqtt.publish(discovery_topic, "", retain=True, qos=1)
        log.info("Removed HA discovery for profile select")

    def publish_profile_state(self, active_profile: str | None) -> None:
        """Publish the currently active profile name."""
        state = active_profile if active_profile else PROFILE_NONE
        self._mqtt.publish(PROFILE_STATE_TOPIC, state, retain=True)

    def subscribe_profile_commands(
        self,
        callback: Callable[[str, dict | str], None],
    ) -> None:
        """Subscribe to profile selection commands from HA."""
        self._mqtt.subscribe(PROFILE_COMMAND_TOPIC, callback)
        log.debug("Subscribed to profile commands")

    def publish_sync_sensor(self, group_id: str, group_name: str) -> None:
        """Publish an HA sensor entity that reports a sync group's current color."""
        unique_id = f"homecue_sync_{group_id}"
        discovery_topic = SYNC_DISCOVERY_TOPIC_TEMPLATE.format(unique_id=unique_id)
        discovery_topic = discovery_topic.replace(
            "homeassistant", self._discovery_prefix, 1
        )

        payload = {
            "name": f"{group_name} Sync",
            "unique_id": unique_id,
            "state_topic": SYNC_STATE_TOPIC_TEMPLATE.format(group_id=group_id),
            "value_template": "{{ value_json.state }}",
            "json_attributes_topic": SYNC_STATE_TOPIC_TEMPLATE.format(group_id=group_id),
            "availability": {
                "topic": AVAILABILITY_TOPIC,
                "payload_available": PAYLOAD_ONLINE,
                "payload_not_available": PAYLOAD_OFFLINE,
            },
            "device": {
                "identifiers": ["homecue_service"],
                "name": "HomeCue",
                "manufacturer": "HomeCue",
                "model": "iCUE Bridge",
                "sw_version": __version__,
            },
        }

        self._mqtt.publish(discovery_topic, payload, retain=True, qos=1)
        log.info("Published HA discovery for sync sensor: %s (%s)", group_name, unique_id)

    def remove_sync_sensor(self, group_id: str) -> None:
        """Remove a sync sensor from HA."""
        unique_id = f"homecue_sync_{group_id}"
        discovery_topic = SYNC_DISCOVERY_TOPIC_TEMPLATE.format(unique_id=unique_id)
        discovery_topic = discovery_topic.replace(
            "homeassistant", self._discovery_prefix, 1
        )
        self._mqtt.publish(discovery_topic, "", retain=True, qos=1)

    def publish_sync_state(
        self, group_id: str, r: int, g: int, b: int, brightness: int, is_on: bool
    ) -> None:
        """Publish the current color state of a sync group."""
        state_topic = SYNC_STATE_TOPIC_TEMPLATE.format(group_id=group_id)
        payload = {
            "state": "ON" if is_on else "OFF",
            "r": r,
            "g": g,
            "b": b,
            "brightness": brightness,
            "rgb": [r, g, b],
        }
        self._mqtt.publish(state_topic, payload, retain=True)

    def _discovery_topic(self, unique_id: str) -> str:
        return f"{self._discovery_prefix}/light/{unique_id}/config"
