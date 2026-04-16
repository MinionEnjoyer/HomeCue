"""MQTT client wrapper with Last Will and Testament and auto-reconnect."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Callable

import paho.mqtt.client as mqtt

from homecue.const import AVAILABILITY_TOPIC, PAYLOAD_OFFLINE, PAYLOAD_ONLINE

log = logging.getLogger(__name__)


class MqttClient:
    """Manages the MQTT connection to the Home Assistant broker."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        client_id: str = "homecue",
    ) -> None:
        self._host = host
        self._port = port
        # Append a short random suffix so multiple instances don't kick each other off
        unique_id = f"{client_id}_{uuid.uuid4().hex[:6]}"
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=unique_id,
        )

        if username:
            self._client.username_pw_set(username, password)

        # Last Will: if we disconnect unexpectedly, broker publishes "offline"
        self._client.will_set(
            AVAILABILITY_TOPIC,
            payload=PAYLOAD_OFFLINE,
            qos=1,
            retain=True,
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        self._subscriptions: dict[str, Callable[[str, dict | str], None]] = {}

    def connect(self) -> None:
        """Connect to the MQTT broker and start the network loop."""
        log.info("Connecting to MQTT broker at %s:%d", self._host, self._port)
        self._client.connect(self._host, self._port)
        self._client.loop_start()

    def disconnect(self) -> None:
        """Publish offline status and disconnect cleanly."""
        self.publish(AVAILABILITY_TOPIC, PAYLOAD_OFFLINE, retain=True, qos=1)
        self._client.loop_stop()
        self._client.disconnect()
        log.info("Disconnected from MQTT broker")

    def publish(
        self,
        topic: str,
        payload: Any,
        retain: bool = False,
        qos: int = 0,
    ) -> None:
        """Publish a message. Dicts are JSON-serialized automatically."""
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        self._client.publish(topic, payload=payload, retain=retain, qos=qos)

    def subscribe(
        self,
        topic: str,
        callback: Callable[[str, dict | str], None],
    ) -> None:
        """Subscribe to a topic with a callback.

        The callback receives (topic, payload) where payload is a parsed dict
        for JSON messages or a raw string otherwise.
        """
        self._subscriptions[topic] = callback
        self._client.subscribe(topic, qos=1)
        self._client.message_callback_add(topic, self._make_handler(callback))
        log.debug("Subscribed to %s", topic)

    def _make_handler(
        self, callback: Callable[[str, dict | str], None]
    ) -> Callable:
        """Wrap a user callback into a paho on_message handler."""

        def handler(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
            topic = message.topic
            raw = message.payload.decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                payload = raw
            try:
                callback(topic, payload)
            except Exception:
                log.exception("Error in MQTT callback for %s", topic)

        return handler

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Any,
    ) -> None:
        """Called when the client connects to the broker."""
        if reason_code == 0:
            log.info("Connected to MQTT broker")
            # Publish online availability
            self.publish(AVAILABILITY_TOPIC, PAYLOAD_ONLINE, retain=True, qos=1)
            # Re-subscribe to all topics on reconnect
            for topic, callback in self._subscriptions.items():
                self._client.subscribe(topic, qos=1)
                self._client.message_callback_add(topic, self._make_handler(callback))
        else:
            log.error("MQTT connection failed: %s", reason_code)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Any,
    ) -> None:
        """Called when the client disconnects from the broker."""
        if reason_code == 0:
            log.info("MQTT disconnected cleanly")
        else:
            log.warning("MQTT disconnected unexpectedly (rc=%s), will reconnect", reason_code)
