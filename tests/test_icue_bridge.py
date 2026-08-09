from unittest.mock import Mock

from cuesdk import CorsairAccessLevel, CorsairDeviceInfo, CorsairDeviceType, CorsairError

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
    sdk.request_control.return_value = CorsairError(CorsairError.CE_Success)
    bridge = IcueBridge()
    bridge._sdk = sdk
    bridge._connected.set()

    devices = bridge.discover_devices()

    assert [device.model for device in devices] == ["K100"]
    assert sdk.get_devices.call_count == 1 + 13
    sdk.request_control.assert_called_once_with("keyboard-1", CorsairAccessLevel.CAL_Shared)


def test_disconnect_closes_the_native_sdk_session():
    sdk = Mock()
    sdk.disconnect.return_value = CorsairError(CorsairError.CE_Success)
    bridge = IcueBridge()
    bridge._sdk = sdk
    bridge._connected.set()
    bridge.disconnect()
    sdk.disconnect.assert_called_once()
    assert not bridge.is_connected
