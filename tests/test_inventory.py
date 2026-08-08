import json
from pathlib import Path

from homecue.icue.devices import CorsairDevice
from homecue.inventory import InventoryStore


def test_inventory_snapshot_is_atomic_and_capability_driven(tmp_path: Path) -> None:
    path = tmp_path / "state" / "inventory.json"
    device = CorsairDevice("sdk-id", "Commander", "Commander", "LED Controller", 2, [10, 11])
    InventoryStore(path).write([device], connected=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["connected"] is True
    assert payload["count"] == 1
    assert payload["devices"][0]["id"] == device.unique_id
    assert payload["devices"][0]["capabilities"] == ["lighting", "brightness", "effects", "individual-leds"]
    assert not path.with_suffix(".tmp").exists()


def test_inventory_can_report_clean_disconnect(tmp_path: Path) -> None:
    path = tmp_path / "inventory.json"
    store = InventoryStore(path)
    store.write([], connected=False)
    assert json.loads(path.read_text(encoding="utf-8")) == {"connected": False, "count": 0, "devices": []}
