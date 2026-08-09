"""Hardware-free contract tests for the native iCUE SDK boundary."""

from types import SimpleNamespace
from unittest.mock import Mock
import threading

import pytest
from cuesdk import (
    CorsairAccessLevel,
    CorsairDeviceInfo,
    CorsairDeviceType,
    CorsairError,
    CorsairLedPosition,
    CorsairSessionState,
)

from homecue.icue.bridge import IcueBridge, _DEVICE_TYPE_MASKS


SUCCESS = CorsairError(CorsairError.CE_Success)
FAILURE = CorsairError(CorsairError.CE_NotConnected)


def make_bridge(
    sdk: Mock,
    *,
    connected: bool = False,
    exclusive: bool = False,
    on_devices_changed=None,
) -> IcueBridge:
    """Build the bridge around a fake without loading Corsair's native DLL."""
    bridge = IcueBridge.__new__(IcueBridge)
    bridge._sdk = sdk
    bridge._exclusive = exclusive
    bridge._on_devices_changed = on_devices_changed
    bridge._connected = threading.Event()
    if connected:
        bridge._connected.set()
    bridge._devices = {}
    bridge._lock = threading.Lock()
    return bridge


def device_info(
    device_id: str = "link-hub-1",
    model: str = "iCUE LINK System Hub",
    device_type: int = CorsairDeviceType.CDT_LedController,
) -> CorsairDeviceInfo:
    return CorsairDeviceInfo(
        type=CorsairDeviceType(device_type),
        device_id=device_id,
        serial=f"serial-{device_id}",
        model=model,
        led_count=2,
        channel_count=2,
    )


@pytest.fixture
def sdk() -> Mock:
    native = Mock()
    native.disconnect.return_value = SUCCESS
    native.request_control.return_value = SUCCESS
    native.release_control.return_value = SUCCESS
    native.set_led_colors.return_value = SUCCESS
    return native


@pytest.fixture
def bridge(sdk: Mock) -> IcueBridge:
    return make_bridge(sdk, connected=True)


def configure_device(sdk: Mock, info: CorsairDeviceInfo) -> None:
    sdk.get_device_info.return_value = info, SUCCESS
    sdk.get_led_positions.return_value = [
        CorsairLedPosition(11, 0.0, 0.0),
        CorsairLedPosition(12, 1.0, 0.0),
    ], SUCCESS


def test_connect_waits_for_connected_callback_and_reads_versions(sdk: Mock) -> None:
    bridge = make_bridge(sdk)

    def connect(callback):
        callback(SimpleNamespace(state=CorsairSessionState.CSS_Connected))
        return SUCCESS

    sdk.connect.side_effect = connect
    sdk.get_session_details.return_value = SimpleNamespace(
        server_version="4.0.18", client_version="4.0.18", server_host_version="5.49.34"
    ), SUCCESS

    assert bridge.connect(timeout=0.01)
    sdk.get_session_details.assert_called_once()


def test_connect_rejects_native_start_failure(sdk: Mock) -> None:
    bridge = make_bridge(sdk)
    sdk.connect.return_value = FAILURE

    assert not bridge.connect(timeout=0.01)
    sdk.get_session_details.assert_not_called()


def test_connect_times_out_without_connected_callback(sdk: Mock) -> None:
    bridge = make_bridge(sdk)
    sdk.connect.return_value = SUCCESS

    assert not bridge.connect(timeout=0)


@pytest.mark.parametrize(
    "state",
    [
        CorsairSessionState.CSS_ConnectionLost,
        CorsairSessionState.CSS_Timeout,
        CorsairSessionState.CSS_ConnectionRefused,
    ],
)
def test_failure_session_states_clear_connection(bridge: IcueBridge, state: int) -> None:
    bridge._on_session_state_changed(SimpleNamespace(state=state))
    assert not bridge.is_connected


def test_discovery_uses_all_device_query_when_available(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()
    sdk.get_devices.return_value = [hub], SUCCESS
    configure_device(sdk, hub)

    devices = bridge.discover_devices()

    assert [(item.model, item.led_ids) for item in devices] == [
        ("iCUE LINK System Hub", [11, 12])
    ]
    sdk.get_devices.assert_called_once()
    sdk.request_control.assert_called_once_with("link-hub-1", CorsairAccessLevel.CAL_Shared)


def test_discovery_falls_back_to_categories_and_deduplicates(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()

    def get_devices(device_filter):
        if device_filter.device_type_mask in (
            CorsairDeviceType.CDT_LedController,
            CorsairDeviceType.CDT_Cooler,
        ):
            return [hub], SUCCESS
        return [], SUCCESS

    sdk.get_devices.side_effect = get_devices
    configure_device(sdk, hub)

    devices = bridge.discover_devices()

    assert [item.device_id for item in devices] == ["link-hub-1"]
    assert sdk.get_devices.call_count == 1 + len(_DEVICE_TYPE_MASKS)
    sdk.request_control.assert_called_once_with("link-hub-1", CorsairAccessLevel.CAL_Shared)


def test_category_errors_do_not_hide_devices_from_other_categories(
    bridge: IcueBridge, sdk: Mock
) -> None:
    keyboard = device_info("keyboard-1", "K100", CorsairDeviceType.CDT_Keyboard)

    def get_devices(device_filter):
        if device_filter.device_type_mask == CorsairDeviceType.CDT_Mouse:
            return [], FAILURE
        if device_filter.device_type_mask == CorsairDeviceType.CDT_Keyboard:
            return [keyboard], SUCCESS
        return [], SUCCESS

    sdk.get_devices.side_effect = get_devices
    configure_device(sdk, keyboard)

    assert [item.model for item in bridge.discover_devices()] == ["K100"]


def test_primary_enumeration_error_does_not_attempt_fallback(bridge: IcueBridge, sdk: Mock) -> None:
    sdk.get_devices.return_value = [], FAILURE
    assert bridge.discover_devices() == []
    sdk.get_devices.assert_called_once()


def test_discovery_skips_device_when_info_lookup_fails(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()
    sdk.get_devices.return_value = [hub], SUCCESS
    sdk.get_device_info.return_value = None, FAILURE
    assert bridge.discover_devices() == []
    sdk.request_control.assert_not_called()


def test_discovery_keeps_device_when_led_lookup_fails(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()
    sdk.get_devices.return_value = [hub], SUCCESS
    sdk.get_device_info.return_value = hub, SUCCESS
    sdk.get_led_positions.return_value = [], FAILURE

    devices = bridge.discover_devices()

    assert len(devices) == 1
    assert devices[0].led_ids == []


def test_exclusive_mode_requests_and_releases_exclusive_control(sdk: Mock) -> None:
    hub = device_info()
    bridge = make_bridge(sdk, connected=True, exclusive=True)
    sdk.get_devices.return_value = [hub], SUCCESS
    configure_device(sdk, hub)

    bridge.discover_devices()
    bridge.disconnect()

    sdk.request_control.assert_called_once_with(
        "link-hub-1", CorsairAccessLevel.CAL_ExclusiveLightingControl
    )
    sdk.release_control.assert_called_once_with("link-hub-1")
    sdk.disconnect.assert_called_once()


def test_disconnect_closes_native_session_even_when_it_reports_failure(
    bridge: IcueBridge, sdk: Mock
) -> None:
    sdk.disconnect.return_value = FAILURE
    bridge.disconnect()
    sdk.disconnect.assert_called_once()
    assert not bridge.is_connected


def test_set_device_color_writes_every_discovered_led(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()
    sdk.get_devices.return_value = [hub], SUCCESS
    configure_device(sdk, hub)
    bridge.discover_devices()

    assert bridge.set_device_color("link-hub-1", 10, 20, 30)
    device_id, colors = sdk.set_led_colors.call_args.args
    assert device_id == "link-hub-1"
    assert [(color.id, color.r, color.g, color.b, color.a) for color in colors] == [
        (11, 10, 20, 30, 255),
        (12, 10, 20, 30, 255),
    ]


def test_set_single_led_rejects_unknown_device_and_led(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()
    sdk.get_devices.return_value = [hub], SUCCESS
    configure_device(sdk, hub)
    bridge.discover_devices()

    assert not bridge.set_led_color("missing", 11, 1, 2, 3)
    assert not bridge.set_led_color("link-hub-1", 99, 1, 2, 3)
    sdk.set_led_colors.assert_not_called()


def test_color_write_failure_is_returned_to_caller(bridge: IcueBridge, sdk: Mock) -> None:
    hub = device_info()
    sdk.get_devices.return_value = [hub], SUCCESS
    configure_device(sdk, hub)
    bridge.discover_devices()
    sdk.set_led_colors.return_value = FAILURE

    assert not bridge.set_led_color("link-hub-1", 11, 1, 2, 3)


def test_device_callback_notifies_only_after_inventory_exists(sdk: Mock) -> None:
    changed = Mock()
    bridge = make_bridge(sdk, on_devices_changed=changed)
    bridge._on_device_event(SimpleNamespace())
    changed.assert_not_called()

    bridge._devices["link-hub-1"] = Mock()
    bridge._on_device_event(SimpleNamespace())
    changed.assert_called_once()
