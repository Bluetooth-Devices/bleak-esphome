import asyncio
import dataclasses

import pytest
from aioesphomeapi import (
    APIClient,
    BluetoothProxyFeature,
    BluetoothScannerMode,
    BluetoothScannerState,
    BluetoothScannerStateResponse,
    DeviceInfo,
)
from habluetooth import BluetoothScanningMode

from bleak_esphome.backend import scanner as scanner_module
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.connect import _can_connect, connect_scanner


@pytest.mark.asyncio
async def test_connect(mock_client: APIClient) -> None:
    """Test the connect_scanner function."""
    device_info = await mock_client.device_info()
    scanner = connect_scanner(mock_client, device_info, available=True)
    assert scanner is not None
    assert (
        scanner.device_info.bluetooth_mac_address == device_info.bluetooth_mac_address
    )
    assert scanner.client is mock_client


@pytest.mark.asyncio
async def test_connect_passive_only(
    mock_client: APIClient, mock_device_info: DeviceInfo
) -> None:
    """A passive-only proxy must not subscribe to connection slot updates."""
    info = dataclasses.replace(
        mock_device_info,
        bluetooth_proxy_feature_flags=(
            BluetoothProxyFeature.PASSIVE_SCAN
            | BluetoothProxyFeature.RAW_ADVERTISEMENTS
        ),
    )
    client_data = connect_scanner(mock_client, info, available=True)
    assert client_data is not None
    mock_client.subscribe_bluetooth_connections_free.assert_not_called()
    mock_client.subscribe_bluetooth_le_raw_advertisements.assert_called_once()
    mock_client.subscribe_bluetooth_le_advertisements.assert_not_called()


@pytest.mark.asyncio
async def test_connect_full_feature_subscribes_all(mock_client: APIClient) -> None:
    """A full-feature proxy subscribes to slots, scanner state, and raw adv."""
    device_info = await mock_client.device_info()
    client_data = connect_scanner(mock_client, device_info, available=True)
    assert client_data is not None
    mock_client.subscribe_bluetooth_connections_free.assert_called_once()
    mock_client.subscribe_bluetooth_scanner_state.assert_called_once()
    mock_client.subscribe_bluetooth_le_raw_advertisements.assert_called_once()
    mock_client.subscribe_bluetooth_le_advertisements.assert_not_called()


@pytest.mark.asyncio
async def test_connect_state_and_mode_binds_client(mock_client: APIClient) -> None:
    """FEATURE_STATE_AND_MODE wires the scanner so mode control reaches the proxy."""
    device_info = await mock_client.device_info()
    client_data = connect_scanner(mock_client, device_info, available=True)
    assert client_data.scanner is not None
    # The client is bound only via the FEATURE_STATE_AND_MODE branch; without
    # it async_set_scanning_mode would no-op. A firmware command proves wiring.
    client_data.scanner.async_set_scanning_mode(BluetoothScanningMode.ACTIVE)
    mock_client.bluetooth_scanner_set_mode.assert_called_once_with(
        BluetoothScannerMode.ACTIVE
    )


@pytest.mark.asyncio
async def test_connect_fixed_mode_reports_state_without_mode_control(
    mock_client: APIClient, mock_device_info: DeviceInfo
) -> None:
    """A fixed-active raw proxy can report status without accepting commands."""
    info = dataclasses.replace(
        mock_device_info,
        bluetooth_proxy_feature_flags=(
            BluetoothProxyFeature.PASSIVE_SCAN
            | BluetoothProxyFeature.ACTIVE_CONNECTIONS
            | BluetoothProxyFeature.REMOTE_CACHING
            | BluetoothProxyFeature.PAIRING
            | BluetoothProxyFeature.RAW_ADVERTISEMENTS
        ),
    )
    running = BluetoothScannerStateResponse(
        state=BluetoothScannerState.RUNNING,
        mode=BluetoothScannerMode.ACTIVE,
        configured_mode=BluetoothScannerMode.ACTIVE,
    )

    def subscribe_raw(_on_advertisements: object) -> None:
        # The first report can arrive as soon as the subscribe is sent.
        registration = mock_client.subscribe_bluetooth_scanner_state.call_args
        if registration is not None:
            (report_state,) = registration.args
            report_state(running)

    mock_client.subscribe_bluetooth_le_raw_advertisements.side_effect = subscribe_raw
    client_data = connect_scanner(mock_client, info, available=True)
    scanner = client_data.scanner
    assert scanner is not None
    active = BluetoothScanningMode.ACTIVE
    assert scanner.current_mode == active
    assert scanner.requested_mode == active
    assert scanner.configured_mode == active

    mock_client.subscribe_bluetooth_scanner_state.assert_called_once()
    (report_state,) = mock_client.subscribe_bluetooth_scanner_state.call_args.args
    for state, current_mode in (
        (BluetoothScannerState.STOPPED, None),
        (BluetoothScannerState.RUNNING, active),
    ):
        report_state(dataclasses.replace(running, state=state))
        assert scanner.current_mode == current_mode
        assert scanner.requested_mode == active
        assert scanner.configured_mode == active

    assert await scanner.async_request_active_window(0) is False
    scanner.async_set_scanning_mode(BluetoothScanningMode.PASSIVE)
    mock_client.bluetooth_scanner_set_mode.assert_not_called()


@pytest.mark.asyncio
async def test_connect_decoded_advertisements(
    mock_client: APIClient, mock_device_info: DeviceInfo
) -> None:
    """When RAW_ADVERTISEMENTS is absent, decoded subscription is used."""
    info = dataclasses.replace(
        mock_device_info,
        bluetooth_proxy_feature_flags=BluetoothProxyFeature.PASSIVE_SCAN,
    )
    client_data = connect_scanner(mock_client, info, available=True)
    assert client_data is not None
    mock_client.subscribe_bluetooth_le_advertisements.assert_called_once()
    mock_client.subscribe_bluetooth_le_raw_advertisements.assert_not_called()
    mock_client.subscribe_bluetooth_scanner_state.assert_not_called()


@pytest.mark.asyncio
async def test_can_connect_true() -> None:
    """`_can_connect` returns True when device is available and has a free slot."""
    device = ESPHomeBluetoothDevice("proxy", "AA:BB:CC:DD:EE:FF", available=True)
    device.ble_connections_free = 2
    assert _can_connect(device, "AA:BB:CC:DD:EE:FF") is True


@pytest.mark.asyncio
async def test_can_connect_no_free_slots() -> None:
    """`_can_connect` returns False when no slots are free, even if available."""
    device = ESPHomeBluetoothDevice("proxy", "AA:BB:CC:DD:EE:FF", available=True)
    device.ble_connections_free = 0
    assert _can_connect(device, "AA:BB:CC:DD:EE:FF") is False


@pytest.mark.asyncio
async def test_can_connect_unavailable() -> None:
    """`_can_connect` returns False when the proxy is unavailable."""
    device = ESPHomeBluetoothDevice("proxy", "AA:BB:CC:DD:EE:FF", available=False)
    device.ble_connections_free = 2
    assert _can_connect(device, "AA:BB:CC:DD:EE:FF") is False


@pytest.mark.asyncio
async def test_connect_arms_subscription_watchdog(
    mock_client: APIClient, mock_device_info: DeviceInfo
) -> None:
    """RAW_ADVERTISEMENTS with FEATURE_STATE_AND_MODE arms the resubscribe."""
    client_data = connect_scanner(mock_client, mock_device_info, available=True)
    scanner = client_data.scanner
    assert scanner is not None
    assert scanner._resubscribe_advertisements is not None
    mock_client.subscribe_bluetooth_le_raw_advertisements.assert_called_once()
    # The armed callback re-issues the exact same subscribe call.
    scanner._resubscribe_advertisements()
    assert mock_client.subscribe_bluetooth_le_raw_advertisements.call_count == 2
    first, second = mock_client.subscribe_bluetooth_le_raw_advertisements.call_args_list
    assert first == second


@pytest.mark.asyncio
async def test_connect_no_watchdog_without_state_and_mode(
    mock_client: APIClient,
    mock_device_info: DeviceInfo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silence from a legacy raw proxy must not trigger resubscription."""
    monkeypatch.setattr(scanner_module, "_SUBSCRIPTION_RETRY_DELAYS", (0.0,))
    info = dataclasses.replace(
        mock_device_info,
        bluetooth_proxy_feature_flags=(
            BluetoothProxyFeature.PASSIVE_SCAN
            | BluetoothProxyFeature.RAW_ADVERTISEMENTS
        ),
    )
    client_data = connect_scanner(mock_client, info, available=True)
    scanner = client_data.scanner
    assert scanner is not None
    unsetup = scanner.async_setup()
    try:
        # Let a wrongly armed watchdog start and pass its first delay.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_client.subscribe_bluetooth_le_raw_advertisements.assert_called_once()
        assert scanner.current_mode is None
        assert scanner.requested_mode is None
    finally:
        unsetup()
