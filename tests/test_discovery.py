from typing import Any, Callable

from homecue.icue.devices import CorsairDevice
from homecue.mqtt.discovery import HaDiscovery


class FakeMqtt:
    def __init__(self) -> None:
        self.published: list[tuple[str, Any, bool, int]] = []
        self.subscriptions: list[tuple[str, Callable]] = []

    def publish(self, topic: str, payload: Any, retain: bool = False, qos: int = 0) -> None:
        self.published.append((topic, payload, retain, qos))

    def subscribe(self, topic: str, callback: Callable) -> None:
        self.subscriptions.append((topic, callback))


def test_discovery_payload_uses_custom_prefix_and_device_contract() -> None:
    mqtt = FakeMqtt()
    target = CorsairDevice("id", "Desk lights", "Commander", "controller", 24)
    discovery = HaDiscovery(mqtt, "custom")  # type: ignore[arg-type]
    discovery.publish_discovery(target)
    topic, payload, retain, qos = mqtt.published[-1]
    assert topic == f"custom/light/{target.unique_id}/config"
    assert payload["command_topic"].endswith(f"/{target.unique_id}/set")
    assert payload["device"]["manufacturer"] == "Corsair"
    assert payload["supported_color_modes"] == ["rgb"]
    assert (retain, qos) == (True, 1)


def test_state_and_removal_publish_retained_messages() -> None:
    mqtt = FakeMqtt()
    target = CorsairDevice("id", "Desk lights", "Commander", "controller", 24)
    discovery = HaDiscovery(mqtt)  # type: ignore[arg-type]
    discovery.publish_state(target)
    assert mqtt.published[-1][1]["state"] == "ON"
    assert mqtt.published[-1][2] is True
    discovery.remove_discovery(target)
    assert mqtt.published[-1][1] == ""
    assert mqtt.published[-1][3] == 1


def test_sync_sensor_contract() -> None:
    mqtt = FakeMqtt()
    discovery = HaDiscovery(mqtt, "custom")  # type: ignore[arg-type]
    discovery.publish_sync_sensor("desk", "Desk")
    assert mqtt.published[-1][0] == "custom/sensor/homecue_sync_desk/config"
    discovery.publish_sync_state("desk", 1, 2, 3, 128, True)
    assert mqtt.published[-1][1] == {
        "state": "ON", "r": 1, "g": 2, "b": 3, "brightness": 128, "rgb": [1, 2, 3]
    }


def test_inventory_groups_devices_in_suggested_area() -> None:
    mqtt = FakeMqtt()
    target = CorsairDevice("id", "Desk lights", "Commander", "controller", 2, [10, 11])
    discovery = HaDiscovery(mqtt, "custom", "Gaming Room")  # type: ignore[arg-type]
    discovery.publish_inventory([target])
    config_payload = mqtt.published[-2][1]
    state_payload = mqtt.published[-1][1]
    assert config_payload["device"]["suggested_area"] == "Gaming Room"
    assert state_payload["count"] == 1
    assert state_payload["devices"][0]["led_count"] == 2

    discovery.publish_inventory([])
    assert mqtt.published[-1][1] == {"count": 0, "devices": []}


def test_individual_led_discovery_and_state_contract() -> None:
    mqtt = FakeMqtt()
    target = CorsairDevice("id", "Desk lights", "Commander", "controller", 1, [42])
    discovery = HaDiscovery(mqtt, "custom", "Gaming Room")  # type: ignore[arg-type]
    discovery.publish_led_discovery(target, 42)
    topic, payload, retain, qos = mqtt.published[-1]
    assert topic == f"custom/light/{target.unique_id}_led_42/config"
    assert payload["name"] == "LED 42"
    assert payload["device"]["identifiers"] == [target.unique_id]
    assert payload["device"]["suggested_area"] == "Gaming Room"
    assert (retain, qos) == (True, 1)

    callback = lambda *_: None
    discovery.subscribe_led_commands(target, 42, callback)
    assert mqtt.subscriptions[-1][0].endswith("/led/42/set")
    discovery.publish_led_state(target, 42, {"state": "ON"})
    assert mqtt.published[-1][0].endswith("/led/42/state")
