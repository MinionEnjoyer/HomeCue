import json
from pathlib import Path
from types import SimpleNamespace

from homecue.icue import native_probe


def test_native_probe_parses_direct_sdk_inventory(
    tmp_path: Path, monkeypatch
) -> None:
    probe = tmp_path / "homecue-icue-probe.exe"
    probe.write_bytes(b"probe")
    payload = {
        "connected": True,
        "enumerationError": 0,
        "devices": [
            {
                "id": "native-hub-1",
                "model": "iCUE LINK System Hub",
                "type": 64,
                "ledIds": [1, 2, 3],
            }
        ],
    }
    monkeypatch.setenv("HOMECUE_ICUE_PROBE", str(probe))
    monkeypatch.setattr(
        native_probe.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=json.dumps(payload), returncode=0
        ),
    )

    devices = native_probe.enumerate_native_devices()

    assert len(devices) == 1
    assert devices[0].device_id == "native-hub-1"
    assert devices[0].led_ids == [1, 2, 3]


def test_native_probe_returns_empty_inventory_for_invalid_output(
    tmp_path: Path, monkeypatch
) -> None:
    probe = tmp_path / "homecue-icue-probe.exe"
    probe.write_bytes(b"probe")
    monkeypatch.setenv("HOMECUE_ICUE_PROBE", str(probe))
    monkeypatch.setattr(
        native_probe.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="not-json", returncode=1),
    )

    assert native_probe.enumerate_native_devices() == []
