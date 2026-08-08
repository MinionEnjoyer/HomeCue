from pathlib import Path

import pytest

from homecue.config import load_config


def test_load_config_uses_safe_defaults_for_missing_file(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.yaml")
    assert config.mqtt.host == "localhost"
    assert config.mqtt.port == 1883
    assert config.effects_fps == 30
    assert config.home_assistant is None


def test_load_config_reads_connections_and_runtime(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
mqtt:
  host: broker.local
  port: 1884
  username: cue
  discovery_prefix: ha
home_assistant:
  url: http://ha.local:8123
  token: secret
poll_interval: 1.5
effects_fps: 60
exclusive_access: true
""",
        encoding="utf-8",
    )
    config = load_config(path)
    assert (config.mqtt.host, config.mqtt.port, config.mqtt.username) == ("broker.local", 1884, "cue")
    assert config.home_assistant and config.home_assistant.url == "http://ha.local:8123"
    assert config.poll_interval == pytest.approx(1.5)
    assert config.effects_fps == 60
    assert config.exclusive_access is True
