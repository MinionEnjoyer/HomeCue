from types import SimpleNamespace
from unittest.mock import Mock

from cuesdk import CorsairDeviceInfo, CorsairDeviceType, CorsairError, CorsairSessionState

from homecue.icue.bridge import IcueBridge


def test_discovery_falls_back_to_category_filters():
    sdk = Mock()
    keyboard = CorsairDeviceInfo(
        type=CorsairDeviceType(CorsairDeviceType.CDT_Keyboard),
        device_id="keyboard-1",
        serial="serial",
        model="K100",
        led_count=2,
        channel_count=0,
    )

    def get_devices(device_filter):
        if device_filter.device_type_mask == CorsairDeviceType.CDT_Keyboard:
            return [keyboard], CorsairError(CorsairError.CE_Success)
        return [], CorsairError(CorsairError.CE_Success)

    sdk.get_devices.side_effect = get_devices
    sdk.get_device_info.return_value = keyboard, CorsairError(CorsairError.CE_Success)
    sdk.get_led_positions.return_value = [], CorsairError(CorsairError.CE_Success)
    bridge = IcueBridge()
    bridge._sdk = sdk
    bridge._connected.set()

    devices = bridge.discover_devices()

    assert [device.model for device in devices] == ["K100"]
    assert sdk.get_devices.call_count == 1 + 13


def test_subscribes_during_connected_transition_and_uses_announced_ids():
    sdk = Mock()
    sdk.subscribe_for_events.return_value = CorsairError(CorsairError.CE_Success)
    sdk.get_devices.return_value = [], CorsairError(CorsairError.CE_Success)
    hub = CorsairDeviceInfo(
        type=CorsairDeviceType(CorsairDeviceType.CDT_LedController),
        device_id="link-hub-1",
        serial="serial",
        model="iCUE LINK System Hub",
        led_count=34,
        channel_count=2,
    )
    sdk.get_device_info.return_value = hub, CorsairError(CorsairError.CE_Success)
    sdk.get_led_positions.return_value = [], CorsairError(CorsairError.CE_Success)
    bridge = IcueBridge()
    bridge._sdk = sdk

    bridge._on_session_state_changed(SimpleNamespace(state=CorsairSessionState.CSS_Connected))
    bridge._on_device_event(SimpleNamespace(data=SimpleNamespace(device_id="link-hub-1", is_connected=True)))
    devices = bridge.discover_devices()

    sdk.subscribe_for_events.assert_called_once()
    assert [device.model for device in devices] == ["iCUE LINK System Hub"]
