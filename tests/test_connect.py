import dataclasses

import pytest
from aioesphomeapi import APIClient, BluetoothProxyFeature, DeviceInfo

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
    mock_client.subscribe_bluetooth_scanner_state.assert_not_called()
    mock_client.subscribe_bluetooth_le_raw_advertisements.assert_called_once()
    mock_client.subscribe_bluetooth_le_advertisements.assert_not_called()


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
async def test_connect_captures_unsubscribe_callbacks(
    mock_client: APIClient, mock_device_info: DeviceInfo
) -> None:
    """
    ``connect_scanner`` captures unsubscribe handles for every subscription.

    The persistent ``APIClient`` is reused across reconnects, so subscriptions
    must be torn down on disconnect. Capturing the handles is what makes that
    possible.
    """
    client_data = connect_scanner(mock_client, mock_device_info, available=True)
    # mock_device_info enables ACTIVE_CONNECTIONS, FEATURE_STATE_AND_MODE and
    # RAW_ADVERTISEMENTS — three feature-gated subscriptions in total.
    assert len(client_data.unsubscribe_callbacks) == 3
    assert all(callable(cb) for cb in client_data.unsubscribe_callbacks)


@pytest.mark.asyncio
async def test_connect_passive_only_captures_single_unsubscribe(
    mock_client: APIClient, mock_device_info: DeviceInfo
) -> None:
    """Passive proxy only subscribes to raw advertisements, so one unsubscribe."""
    info = dataclasses.replace(
        mock_device_info,
        bluetooth_proxy_feature_flags=(
            BluetoothProxyFeature.PASSIVE_SCAN
            | BluetoothProxyFeature.RAW_ADVERTISEMENTS
        ),
    )
    client_data = connect_scanner(mock_client, info, available=True)
    assert len(client_data.unsubscribe_callbacks) == 1


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
