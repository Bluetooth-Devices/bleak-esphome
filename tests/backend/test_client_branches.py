"""
Targeted coverage for ``bleak_esphome.backend.client`` branches.

Exercises smaller helper paths in :mod:`bleak_esphome.backend.client`
not reached by the main connect/services test suite: the
``api_error_as_bleak_error`` decorator, the
``_on_bluetooth_connection_state`` error/disconnect arms, ``clear_cache``,
``write_gatt_descriptor``, ``stop_notify``, and the ``start_notify``
guard clauses.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aioesphomeapi import (
    BLEConnectionError,
    BluetoothConnectionDroppedError,
    BluetoothDeviceClearCache,
    BluetoothProxyFeature,
    ESPHomeBluetoothGATTServices,
)
from aioesphomeapi.core import (
    BluetoothGATTAPIError,
    BluetoothGATTError,
    TimeoutAPIError,
)
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError

from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData

from ._helpers import ESP_MAC_ADDRESS, _make_client


@pytest.mark.asyncio
async def test_str_returns_description(client_data: ESPHomeClientData) -> None:
    """``__str__`` returns the human-readable description."""
    client = _make_client(client_data)
    text = str(client)
    assert text.startswith("ESPHomeClient (")
    assert ESP_MAC_ADDRESS in text


@pytest.mark.asyncio
async def test_timeout_api_error_becomes_timeout_error(
    client_data: ESPHomeClientData,
) -> None:
    """``TimeoutAPIError`` is converted to :class:`TimeoutError`."""
    client = _make_client(client_data)
    client._is_connected = True
    char = BleakGATTCharacteristic(None, 1, "test", ["read"], lambda: 20, None)
    with (
        patch.object(
            client._client,
            "bluetooth_gatt_read",
            side_effect=TimeoutAPIError("boom"),
        ),
        pytest.raises(TimeoutError, match="boom"),
    ):
        await client.read_gatt_char(char)


@pytest.mark.asyncio
async def test_connection_dropped_marks_disconnected(
    client_data: ESPHomeClientData,
) -> None:
    """``BluetoothConnectionDroppedError`` marks the client disconnected."""
    client = _make_client(client_data)
    client._is_connected = True
    # Register the esp-disconnect callback so we can confirm it is removed.
    client._disconnect_callbacks.add(client._async_esp_disconnected)
    char = BleakGATTCharacteristic(None, 1, "test", ["read"], lambda: 20, None)
    with (
        patch.object(
            client._client,
            "bluetooth_gatt_read",
            side_effect=BluetoothConnectionDroppedError("dropped"),
        ),
        pytest.raises(BleakError, match="dropped"),
    ):
        await client.read_gatt_char(char)
    assert not client.is_connected
    assert client._async_esp_disconnected not in client._disconnect_callbacks


@pytest.mark.asyncio
async def test_gatt_api_error_minus_one_marks_disconnected(
    client_data: ESPHomeClientData,
) -> None:
    """``BluetoothGATTAPIError`` with error code -1 marks disconnected."""
    client = _make_client(client_data)
    client._is_connected = True
    err = BluetoothGATTError(address=client._address_as_int, handle=1, error=-1)
    char = BleakGATTCharacteristic(None, 1, "test", ["read"], lambda: 20, None)
    with (
        patch.object(
            client._client,
            "bluetooth_gatt_read",
            side_effect=BluetoothGATTAPIError(err),
        ),
        pytest.raises(BleakError),
    ):
        await client.read_gatt_char(char)
    assert not client.is_connected


@pytest.mark.asyncio
async def test_gatt_api_error_other_keeps_connected(
    client_data: ESPHomeClientData,
) -> None:
    """Non-disconnect ``BluetoothGATTAPIError`` does not flip the connected flag."""
    client = _make_client(client_data)
    client._is_connected = True
    err = BluetoothGATTError(address=client._address_as_int, handle=1, error=5)
    char = BleakGATTCharacteristic(None, 1, "test", ["read"], lambda: 20, None)
    with (
        patch.object(
            client._client,
            "bluetooth_gatt_read",
            side_effect=BluetoothGATTAPIError(err),
        ),
        pytest.raises(BleakError),
    ):
        await client.read_gatt_char(char)
    # Error code != -1 must not call _async_ble_device_disconnected
    assert client.is_connected


@pytest.mark.asyncio
async def test_on_bluetooth_connection_state_error_sets_exception(
    client_data: ESPHomeClientData,
) -> None:
    """An error code in the connection callback fails the future with BleakError."""
    client = _make_client(client_data)
    fut: asyncio.Future[bool] = client._loop.create_future()
    # Unknown error code falls through to ESPHOME_GATT_ERRORS lookup
    client._on_bluetooth_connection_state(fut, False, 23, 99999)
    assert fut.done()
    with pytest.raises(BleakError, match="while connecting"):
        fut.result()


@pytest.mark.asyncio
async def test_on_bluetooth_connection_state_known_error_uses_name(
    client_data: ESPHomeClientData,
) -> None:
    """A known BLEConnectionError code uses its symbolic name in the message."""
    client = _make_client(client_data)
    fut: asyncio.Future[bool] = client._loop.create_future()
    client._on_bluetooth_connection_state(
        fut, False, 23, BLEConnectionError.ESP_GATT_CONN_TIMEOUT.value
    )
    assert fut.done()
    with pytest.raises(BleakError, match="ESP_GATT_CONN_TIMEOUT"):
        fut.result()


@pytest.mark.asyncio
async def test_on_bluetooth_connection_state_disconnect_fails_future(
    client_data: ESPHomeClientData,
) -> None:
    """connected=False with no error code fails the future as ``Disconnected``."""
    client = _make_client(client_data)
    fut: asyncio.Future[bool] = client._loop.create_future()
    client._on_bluetooth_connection_state(fut, False, 23, 0)
    assert fut.done()
    with pytest.raises(BleakError, match="Disconnected"):
        fut.result()


@pytest.mark.asyncio
async def test_on_bluetooth_connection_state_idempotent_when_future_done(
    client_data: ESPHomeClientData,
) -> None:
    """A second callback invocation with a completed future is a no-op."""
    client = _make_client(client_data)
    fut: asyncio.Future[bool] = client._loop.create_future()
    # First call resolves the future.
    client._on_bluetooth_connection_state(fut, True, 23, 0)
    assert fut.result() is True
    # Second call (disconnect after success) must not raise even though the
    # future is already done.
    client._on_bluetooth_connection_state(fut, False, 23, 0)
    assert not client.is_connected


@pytest.mark.asyncio
async def test_on_bluetooth_connection_state_preserves_cached_mtu(
    client_data: ESPHomeClientData,
) -> None:
    """
    A cached MTU is preserved when the connection-state callback fires.

    ``connect()`` seeds ``self._mtu`` from the cache before issuing the
    proxy ``bluetooth_device_connect`` call, so the connection-state
    callback must not clobber that value (and must not write the
    just-reported ``mtu`` back into the cache).
    """
    client = _make_client(client_data)
    cached_mtu = 100
    reported_mtu = 23
    client._mtu = cached_mtu
    client._cache.clear_gatt_mtu_cache(client._address_as_int)
    fut: asyncio.Future[bool] = client._loop.create_future()
    client._on_bluetooth_connection_state(fut, True, reported_mtu, 0)
    assert fut.result() is True
    assert client._mtu == cached_mtu
    assert client._cache.get_gatt_mtu_cache(client._address_as_int) is None


@pytest.mark.asyncio
async def test_esp_disconnected_invokes_bleak_callback(
    client_data: ESPHomeClientData,
) -> None:
    """The ESP-side disconnect callback fires the bleak disconnect callback once."""
    client = _make_client(client_data)
    client._is_connected = True
    callback = Mock()
    client._disconnected_callback = callback
    client._async_esp_disconnected()
    callback.assert_called_once()
    assert client._disconnected_callback is None


@pytest.mark.asyncio
async def test_esp_disconnected_does_not_refire_callback(
    client_data: ESPHomeClientData,
) -> None:
    """A second ESP disconnect after the callback cleared is a no-op."""
    client = _make_client(client_data)
    client._is_connected = True
    callback = Mock()
    client._disconnected_callback = callback
    client._async_esp_disconnected()
    callback.assert_called_once()
    # Simulate a stale second disconnect: the callback was cleared, and any
    # subsequent disconnect must not refire it.
    client._is_connected = True
    client._async_esp_disconnected()
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_get_services_empty_raises(
    client_data: ESPHomeClientData,
) -> None:
    """An empty services list from the proxy raises a BleakError."""
    client = _make_client(client_data)
    client._is_connected = True
    empty = ESPHomeBluetoothGATTServices(address=client._address_as_int, services=[])
    # Bypass the cache branch by clearing the REMOTE_CACHING flag.
    client._feature_flags &= ~BluetoothProxyFeature.REMOTE_CACHING.value
    with (
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=empty,
        ),
        pytest.raises(BleakError, match="Failed to get services"),
    ):
        await client._get_services()


@pytest.mark.asyncio
async def test_clear_cache_success(client_data: ESPHomeClientData) -> None:
    """``clear_cache`` returns True on a successful ESPHome response."""
    client = _make_client(client_data)
    client._is_connected = True
    resp = BluetoothDeviceClearCache(
        address=client._address_as_int, success=True, error=0
    )
    with patch.object(
        client._client,
        "bluetooth_device_clear_cache",
        return_value=resp,
    ) as mock_clear:
        assert await client.clear_cache() is True
    mock_clear.assert_called_once_with(client._address_as_int)


@pytest.mark.asyncio
async def test_clear_cache_failure_logs_and_returns_false(
    client_data: ESPHomeClientData,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed ESPHome clear-cache response returns False and is logged."""
    client = _make_client(client_data)
    client._is_connected = True
    resp = BluetoothDeviceClearCache(
        address=client._address_as_int, success=False, error=7
    )
    with patch.object(
        client._client,
        "bluetooth_device_clear_cache",
        return_value=resp,
    ):
        assert await client.clear_cache() is False
    assert "Clear cache failed" in caplog.text


@pytest.mark.asyncio
async def test_clear_cache_without_feature_flag_returns_true(
    client_data: ESPHomeClientData,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without the CACHE_CLEARING flag the call short-circuits to True."""
    client = _make_client(client_data)
    client._is_connected = True
    client._feature_flags &= ~BluetoothProxyFeature.CACHE_CLEARING.value
    with patch.object(
        client._client,
        "bluetooth_device_clear_cache",
    ) as mock_clear:
        assert await client.clear_cache() is True
    mock_clear.assert_not_called()
    assert "On device cache clear is not available" in caplog.text


@pytest.mark.asyncio
async def test_write_gatt_descriptor(
    client_data: ESPHomeClientData,
) -> None:
    """``write_gatt_descriptor`` forwards to the proxy with bytes payload."""
    client = _make_client(client_data)
    client._is_connected = True
    desc = Mock()
    desc.handle = 42
    with patch.object(
        client._client,
        "bluetooth_gatt_write_descriptor",
    ) as mock_write:
        await client.write_gatt_descriptor(desc, b"\x01\x00")
    mock_write.assert_called_once_with(client._address_as_int, 42, b"\x01\x00")


@pytest.mark.asyncio
async def test_start_notify_already_enabled_raises(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """A second start_notify on the same handle raises BleakError."""
    client = _make_client(client_data)
    client._is_connected = True
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await client._get_services()
    char = services.get_characteristic("00002a05-0000-1000-8000-00805f9b34fb")
    assert char is not None
    # Pre-populate the cancels dict; the implementation only inspects keys.
    client._notify_cancels[char.handle] = (AsyncMock(), Mock())
    with pytest.raises(BleakError, match="already enabled"):
        await client.start_notify(char, lambda data: None)


@pytest.mark.asyncio
async def test_start_notify_without_notify_property_raises(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Starting notify on a read-only characteristic raises BleakError."""
    client = _make_client(client_data)
    client._is_connected = True
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await client._get_services()
    # handle=3 is read-only (properties=2).
    char = services.get_characteristic("00002a00-0000-1000-8000-00805f9b34fb")
    assert char is not None
    assert "notify" not in char.properties
    assert "indicate" not in char.properties
    with pytest.raises(BleakError, match="does not have notify or indicate"):
        await client.start_notify(char, lambda data: None)


@pytest.mark.asyncio
async def test_start_notify_skips_cccd_without_remote_caching(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Without REMOTE_CACHING the host does not write to the CCCD itself."""
    client = _make_client(client_data)
    client._is_connected = True
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await client._get_services()
    char = services.get_characteristic("00002a05-0000-1000-8000-00805f9b34fb")
    assert char is not None
    # Disable REMOTE_CACHING so start_notify returns before touching the CCCD.
    client._feature_flags &= ~BluetoothProxyFeature.REMOTE_CACHING.value
    mock_stop_notify = AsyncMock()
    with (
        patch.object(
            client._client,
            "bluetooth_gatt_start_notify",
            return_value=(mock_stop_notify, Mock()),
        ),
        patch.object(
            client._client,
            "bluetooth_gatt_write_descriptor",
        ) as mock_write_desc,
    ):
        await client.start_notify(char, lambda data: None)
    mock_write_desc.assert_not_called()
    assert char.handle in client._notify_cancels


@pytest.mark.asyncio
async def test_stop_notify_calls_stop_callback(
    client_data: ESPHomeClientData,
) -> None:
    """``stop_notify`` awaits and removes the stored stop callback."""
    client = _make_client(client_data)
    client._is_connected = True
    stop = AsyncMock()
    abort = Mock()
    char = Mock()
    char.handle = 99
    client._notify_cancels[99] = (stop, abort)
    await client.stop_notify(char)
    stop.assert_awaited_once()
    assert 99 not in client._notify_cancels


@pytest.mark.asyncio
async def test_stop_notify_missing_handle_is_noop(
    client_data: ESPHomeClientData,
) -> None:
    """Stopping notify on an unknown handle is silently a no-op."""
    client = _make_client(client_data)
    client._is_connected = True
    char = Mock()
    char.handle = 1234
    # Must not raise even though 1234 is not in _notify_cancels.
    await client.stop_notify(char)


@pytest.mark.asyncio
async def test_connect_get_services_failure_disconnects(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """A non-cancel failure in ``_get_services`` runs ``_disconnect``."""
    bleak_client, client = bleak_pair

    async def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("services boom")

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(client, "_get_services", side_effect=_boom),
        patch.object(
            client, "_disconnect", new=AsyncMock(return_value=True)
        ) as mock_disc,
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        # Resolve the connection so we proceed into ``_get_services``.
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        with pytest.raises(RuntimeError, match="services boom"):
            await task
    mock_disc.assert_awaited_once()


@pytest.mark.asyncio
async def test_del_warns_when_subscription_still_active(
    client_data: ESPHomeClientData,
) -> None:
    """
    ``__del__`` logs a warning when a connection-state subscription lingers.

    Reaching ``__del__`` with ``_cancel_connection_state`` still set means the
    bleak client was not properly disconnected before destruction; the warning
    is the only signal the operator gets that the subscription leaked.
    """
    client = _make_client(client_data)
    client._cancel_connection_state = Mock()

    with patch("bleak_esphome.backend.client._LOGGER.warning") as mock_warning:
        client.__del__()

    mock_warning.assert_called_once()
    args, _ = mock_warning.call_args
    assert "not properly" in args[0]
    assert args[1] == client._description

    # Clear the subscription so the implicit ``__del__`` that runs when
    # ``client`` goes out of scope does not emit a second (unpatched) warning.
    client._cancel_connection_state = None
