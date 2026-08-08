from homecue.icue.devices import CorsairDevice


def device() -> CorsairDevice:
    return CorsairDevice("device-1", "Desk", "Commander", "controller", 12)


def test_unique_id_is_stable_and_does_not_expose_sdk_id() -> None:
    first = device().unique_id
    assert first == device().unique_id
    assert first.startswith("homecue_")
    assert "device-1" not in first


def test_command_updates_and_clamps_device_state() -> None:
    target = device()
    target.update_from_command(
        {"state": "ON", "brightness": 999, "color": {"r": -5, "g": 100, "b": 300}, "effect": "rainbow"}
    )
    assert target.brightness == 255
    assert (target.r, target.g, target.b) == (0, 100, 255)
    assert target.effect == "rainbow"


def test_effective_color_respects_brightness_and_power() -> None:
    target = device()
    target.update_from_command({"brightness": 128, "color": {"r": 200, "g": 100, "b": 50}})
    assert target.effective_color == (100, 50, 25)
    target.update_from_command({"state": "OFF"})
    assert target.effective_color == (0, 0, 0)
    assert target.to_state_payload()["state"] == "OFF"
