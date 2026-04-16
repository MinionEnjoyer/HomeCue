"""Configuration loading and validation for HomeCue."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from homecue.const import DEFAULT_EFFECTS_FPS, DEFAULT_MQTT_PORT, DEFAULT_POLL_INTERVAL

log = logging.getLogger(__name__)


@dataclass
class MqttConfig:
    """MQTT broker connection settings."""

    host: str = "localhost"
    port: int = DEFAULT_MQTT_PORT
    username: str | None = None
    password: str | None = None
    discovery_prefix: str = "homeassistant"
    client_id: str = "homecue"


@dataclass
class HomeAssistantConfig:
    """Home Assistant REST API settings for associated entities."""

    url: str = "http://localhost:8123"
    token: str = ""


@dataclass
class HomeCueConfig:
    """Top-level HomeCue configuration."""

    mqtt: MqttConfig = field(default_factory=MqttConfig)
    poll_interval: float = DEFAULT_POLL_INTERVAL
    effects_fps: int = DEFAULT_EFFECTS_FPS
    exclusive_access: bool = False
    log_level: str = "INFO"
    device_names: dict[str, str] = field(default_factory=dict)
    profiles_path: str | None = None
    sync_groups: dict[str, str] = field(default_factory=dict)
    home_assistant: HomeAssistantConfig | None = None
    associated_entities: dict[str, list[str]] = field(default_factory=dict)


def load_config(path: str | Path) -> HomeCueConfig:
    """Load configuration from a YAML file.

    Falls back to defaults for any missing values.
    """
    config_path = Path(path)
    if not config_path.exists():
        log.warning("Config file %s not found, using defaults", config_path)
        return HomeCueConfig()

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f) or {}

    mqtt_raw = raw.get("mqtt", {})
    mqtt = MqttConfig(
        host=mqtt_raw.get("host", MqttConfig.host),
        port=mqtt_raw.get("port", MqttConfig.port),
        username=mqtt_raw.get("username"),
        password=mqtt_raw.get("password"),
        discovery_prefix=mqtt_raw.get("discovery_prefix", MqttConfig.discovery_prefix),
        client_id=mqtt_raw.get("client_id", MqttConfig.client_id),
    )

    # Home Assistant REST API (optional)
    ha_config = None
    ha_raw = raw.get("home_assistant")
    if ha_raw and ha_raw.get("token"):
        ha_config = HomeAssistantConfig(
            url=ha_raw.get("url", HomeAssistantConfig.url),
            token=ha_raw["token"],
        )

    return HomeCueConfig(
        mqtt=mqtt,
        poll_interval=raw.get("poll_interval", DEFAULT_POLL_INTERVAL),
        effects_fps=raw.get("effects_fps", DEFAULT_EFFECTS_FPS),
        exclusive_access=raw.get("exclusive_access", False),
        log_level=raw.get("log_level", "INFO"),
        device_names=raw.get("device_names", {}),
        profiles_path=raw.get("profiles_path"),
        sync_groups=raw.get("sync_groups", {}),
        home_assistant=ha_config,
        associated_entities=raw.get("associated_entities", {}),
    )
