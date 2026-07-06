import asyncio
import inspect
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from aioesphomeapi import (
    APIConnectionError,
    BluetoothDevicePairing,
    BluetoothDeviceUnpairing,
    BluetoothProxyFeature,
    ESPHomeBluetoothGATTServices,
)
from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from habluetooth import BaseHaRemoteScanner, HaBluetoothConnector

from bleak_esphome.backend.client import (
    GATT_HEADER_SIZE,
    ESPHomeClient,
    ESPHomeClientData,
)
from bleak_esphome.backend.scanner import ESPHomeScanner

from ._helpers import (
    ESP_MAC_ADDRESS,
    ESP_NAME,
    fetch_services,
    make_bleak_client,
    patch_get_services,
)

PRIMARY_CHAR_UUID = "090b7847-e12b-09a8-b04b-8e0922a9abab"
INDICATE_CHAR_UUID = "00002a05-0000-1000-8000-00805f9b34fb"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"
BLE_ADDRESS_AS_INT = 225106397622015


def test_api_error_decorated_methods_preserve_metadata() -> None:
    """
    Decorated GATT methods expose their own name, docstring, and signature.

    ``api_error_as_bleak_error`` must wrap with ``functools.wraps`` so that
    ``help()``, tracebacks, and signature introspection report the real
    method instead of the internal error-translation wrapper.
    """
    for name in (
        "connect",
        "disconnect",
        "pair",
        "unpair",
        "clear_cache",
        "set_connection_params",
        "read_gatt_char",
        "write_gatt_char",
        "start_notify",
        "stop_notify",
    ):
        method = getattr(ESPHomeClient, name)
        assert method.__name__ == name
        assert method.__doc__ is not None

    # The wrapper must not mask the real signature with (*args, **kwargs).
    params = inspect.signature(ESPHomeClient.connect).parameters
    assert "pair" in params


def test_get_services() -> None:
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)
    assert isinstance(scanner, BaseHaRemoteScanner)


@pytest.mark.asyncio
async def test_client_usage_while_not_connected(
    esphome_client: ESPHomeClient,
) -> None:
    """Test client usage while not connected."""
    with pytest.raises(
        BleakError, match=f"{ESP_NAME}.*{ESP_MAC_ADDRESS}.*not connected"
    ):
        char = BleakGATTCharacteristic(None, 1, "test", [], lambda: 20, None)
        await esphome_client.write_gatt_char(char, b"test", False)


@pytest.mark.asyncio
async def test_client_get_services_and_read_write(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test getting client services and read/write a GATT char."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)

    assert services is not None

    char = services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char is not None
    assert char.uuid == PRIMARY_CHAR_UUID
    assert char.properties == ["read", "write"]
    assert char.handle == 20

    char2 = services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char2 is not None
    assert char2.uuid == PRIMARY_CHAR_UUID
    assert char2.properties == ["read", "write"]
    assert char2.handle == 20

    char3 = services.get_characteristic(UUID(PRIMARY_CHAR_UUID))
    assert char3 is not None
    assert char3.uuid == PRIMARY_CHAR_UUID
    assert char3.properties == ["read", "write"]
    assert char3.handle == 20

    with patch.object(
        connected_client._client,
        "bluetooth_gatt_write",
    ) as mock_write:
        await connected_client.write_gatt_char(char, b"test", True)

    mock_write.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, b"test", True)

    with patch.object(
        connected_client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await connected_client.read_gatt_char(char)

    mock_read.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, 30)


@pytest.mark.asyncio
async def test_client_get_services_max_write_without_response_size(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Every discovered characteristic reports mtu_size - GATT_HEADER_SIZE."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)

    expected = connected_client.mtu_size - GATT_HEADER_SIZE
    chars = [
        char
        for service in services.services.values()
        for char in service.characteristics
    ]
    assert chars, "fixture must expose at least one characteristic"
    for char in chars:
        assert char.max_write_without_response_size == expected


@pytest.mark.asyncio
async def test_client_read_gatt_char_with_custom_timeout(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test reading a GATT char with custom timeout."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char is not None

    with patch.object(
        connected_client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await connected_client.read_gatt_char(char, timeout=90.0)

    mock_read.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, 90.0)


@pytest.mark.asyncio
async def test_client_read_gatt_descriptor_default_timeout(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test reading a GATT descriptor uses the default timeout."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(INDICATE_CHAR_UUID)
    assert char is not None
    descriptor = char.get_descriptor(CCCD_UUID)
    assert descriptor is not None

    with patch.object(
        connected_client._client,
        "bluetooth_gatt_read_descriptor",
    ) as mock_read_descriptor:
        await connected_client.read_gatt_descriptor(descriptor)

    mock_read_descriptor.assert_called_once_with(BLE_ADDRESS_AS_INT, 9, 30.0)


@pytest.mark.asyncio
async def test_client_read_gatt_descriptor_with_custom_timeout(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test reading a GATT descriptor with custom timeout."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(INDICATE_CHAR_UUID)
    assert char is not None
    descriptor = char.get_descriptor(CCCD_UUID)
    assert descriptor is not None

    with patch.object(
        connected_client._client,
        "bluetooth_gatt_read_descriptor",
    ) as mock_read_descriptor:
        await connected_client.read_gatt_descriptor(descriptor, timeout=90.0)

    mock_read_descriptor.assert_called_once_with(BLE_ADDRESS_AS_INT, 9, 90.0)


@pytest.mark.asyncio
async def test_bleak_client_get_services_and_read_write(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test getting client services via the bleak wrapper and read/write."""
    bleak_client, client = bleak_pair
    client._is_connected = True
    # In Bleak 1.0, services are available as a property after connect; trigger
    # service discovery manually since we are mocking the proxy.
    await fetch_services(client, esphome_bluetooth_gatt_services)

    assert bleak_client.services is not None

    char2 = bleak_client.services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char2 is not None
    assert char2.uuid == PRIMARY_CHAR_UUID
    assert char2.properties == ["read", "write"]
    assert char2.handle == 20

    char3 = bleak_client.services.get_characteristic(UUID(PRIMARY_CHAR_UUID))
    assert char3 is not None
    assert char3.uuid == PRIMARY_CHAR_UUID
    assert char3.properties == ["read", "write"]
    assert char3.handle == 20

    char = bleak_client.services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char is not None

    with patch.object(
        client._client,
        "bluetooth_gatt_write",
    ) as mock_write:
        await bleak_client.write_gatt_char(char, b"test", True)

    mock_write.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, b"test", True)

    with patch.object(
        client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await bleak_client.read_gatt_char(char)

    mock_read.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, 30)


@pytest.mark.asyncio
async def test_bleak_client_cached_get_services_and_read_write(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test cached client services via the bleak wrapper and read/write."""
    bleak_client, client = bleak_pair
    client._is_connected = True
    with patch_get_services(client, esphome_bluetooth_gatt_services):
        await client._get_services(dangerous_use_bleak_cache=True)
        services = bleak_client.services

    assert services is not None

    await client._get_services(dangerous_use_bleak_cache=True)
    services2 = bleak_client.services
    assert services2 is not None
    assert services2 == services

    char2 = bleak_client.services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char2 is not None
    assert char2.uuid == PRIMARY_CHAR_UUID
    assert char2.properties == ["read", "write"]
    assert char2.handle == 20

    char3 = bleak_client.services.get_characteristic(UUID(PRIMARY_CHAR_UUID))
    assert char3 is not None
    assert char3.uuid == PRIMARY_CHAR_UUID
    assert char3.properties == ["read", "write"]
    assert char3.handle == 20

    char = bleak_client.services.get_characteristic(PRIMARY_CHAR_UUID)
    assert char is not None

    with patch.object(
        client._client,
        "bluetooth_gatt_write",
    ) as mock_write:
        await bleak_client.write_gatt_char(char, b"test", True)

    mock_write.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, b"test", True)

    with patch.object(
        client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await bleak_client.read_gatt_char(char)

    mock_read.assert_called_once_with(BLE_ADDRESS_AS_INT, 20, 30)


@pytest.mark.asyncio
async def test_bleak_client_connect(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test connect and disconnect when connection slots are available."""
    bleak_client, client = bleak_pair
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        await task

    assert client.is_connected
    assert client._mtu == 23
    with patch.object(
        client._client,
        "bluetooth_device_disconnect",
    ) as mock_disconnect:
        await client.disconnect()

    mock_disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bleak_client_connect_connected_future_cancelled_raises_bleak_error(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test that external cancel of the connected_future raises BleakError.

    Simulates a CancelledError leaking from the ESPHome connect path when the
    connect_future is cancelled externally (not the awaiting task). It should
    be converted to a BleakError so bleak_retry_connector can retry instead of
    letting CancelledError propagate to the caller.
    """
    bleak_client, client = bleak_pair
    original_create_future = client._loop.create_future
    captured: list[asyncio.Future[bool]] = []

    def capturing_create_future() -> asyncio.Future[bool]:
        fut = original_create_future()
        captured.append(fut)
        return fut

    mock_cancel_connection_state = Mock()
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=mock_cancel_connection_state,
        ) as mock_connect,
        patch.object(client._loop, "create_future", capturing_create_future),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_connect.assert_called_once()
        assert len(captured) == 1
        captured[0].cancel()
        with pytest.raises(BleakError, match="cancelled"):
            await task
        assert task.cancelling() == 0

    assert not client.is_connected
    mock_cancel_connection_state.assert_called_once_with()
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
async def test_bleak_client_connect_inner_cancelled_raises_bleak_error(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test inner CancelledError converted to BleakError when task not cancelled.

    If ``bluetooth_device_connect`` itself raises ``CancelledError`` (e.g. an
    internal future was cancelled) while the awaiting task is not being
    cancelled, ``connect`` should raise a ``BleakError`` instead.
    """
    bleak_client, _client = bleak_pair
    with (
        patch.object(
            _client._client,
            "bluetooth_device_connect",
            side_effect=asyncio.CancelledError(),
        ),
        pytest.raises(BleakError, match="cancelled"),
    ):
        await bleak_client.connect(dangerous_use_bleak_cache=True)

    assert not _client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_real_task_cancel_propagates_inner(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test real task cancellation during ``bluetooth_device_connect``.

    When the awaiting task is genuinely cancelled (``task.cancelling() > 0``)
    while inside the ``bluetooth_device_connect`` call, the ``CancelledError``
    must propagate so ``TaskGroup`` / ``asyncio.timeout`` semantics are
    preserved.
    """
    bleak_client, client = bleak_pair
    inside_connect = asyncio.Event()

    async def _hang(*args: Any, **kwargs: Any) -> Any:
        inside_connect.set()
        await asyncio.Event().wait()

    with patch.object(
        client._client,
        "bluetooth_device_connect",
        side_effect=_hang,
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await inside_connect.wait()
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_real_task_cancel_propagates_outer(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test real task cancellation during the outer ``await connected_future``.

    When the awaiting task is genuinely cancelled while parked on the
    second ``await connected_future`` (after ``bluetooth_device_connect``
    has returned), the ``CancelledError`` must propagate via the bare
    ``raise`` so ``TaskGroup`` / ``asyncio.timeout`` semantics are preserved.
    """
    bleak_client, client = bleak_pair
    mock_cancel_connection_state = Mock()
    with patch.object(
        client._client,
        "bluetooth_device_connect",
        return_value=mock_cancel_connection_state,
    ) as mock_connect:
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_connect.assert_called_once()
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    assert not client.is_connected
    mock_cancel_connection_state.assert_called_once_with()
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
async def test_bleak_client_connect_raises_when_device_connect_raises(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test ``bluetooth_device_connect`` raising propagates and cancels future.

    Exercises the ``except Exception`` branch around the
    ``bluetooth_device_connect`` call when ``connected_future`` has not yet
    been resolved. The exception must propagate unchanged and the unresolved
    ``connected_future`` must be cancelled to avoid leaking it.
    """
    bleak_client, client = bleak_pair
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            side_effect=APIConnectionError("boom"),
        ),
        pytest.raises(BleakError, match="boom"),
    ):
        await bleak_client.connect(dangerous_use_bleak_cache=True)

    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_raises_after_connected_future_resolved(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test ``bluetooth_device_connect`` raising after the callback fires.

    Exercises the ``if connected_future.done():`` branch inside the
    ``except Exception`` handler around the ``bluetooth_device_connect``
    call. The callback reports a failed connection (which sets a
    ``BleakError`` on ``connected_future``), then ``bluetooth_device_connect``
    itself raises. The already-resolved future must be drained (with the
    BleakError suppressed) and the original exception must propagate.
    """
    bleak_client, client = bleak_pair

    async def _fire_callback_then_raise(
        address: int,
        on_bluetooth_connection_state: Any,
        **kwargs: Any,
    ) -> None:
        on_bluetooth_connection_state(False, 0, 0)
        raise APIConnectionError("boom")

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            side_effect=_fire_callback_then_raise,
        ),
        pytest.raises(BleakError, match="boom"),
    ):
        await bleak_client.connect(dangerous_use_bleak_cache=True)

    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_inner_cancelled_drains_resolved_future(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test inner CancelledError after the callback fires drains the future.

    Exercises the ``if connected_future.done():`` branch inside the
    ``except asyncio.CancelledError`` handler around the
    ``bluetooth_device_connect`` call. The callback resolves
    ``connected_future`` with a ``BleakError`` (failed connection), then
    ``bluetooth_device_connect`` raises ``CancelledError``. The
    already-resolved future must be drained (BleakError suppressed) before
    the CancelledError is converted to a ``BleakError`` for the caller.
    """
    bleak_client, client = bleak_pair

    async def _fire_callback_then_cancel(
        address: int,
        on_bluetooth_connection_state: Any,
        **kwargs: Any,
    ) -> None:
        on_bluetooth_connection_state(False, 0, 0)
        raise asyncio.CancelledError()

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            side_effect=_fire_callback_then_cancel,
        ),
        pytest.raises(BleakError, match="cancelled"),
    ):
        await bleak_client.connect(dangerous_use_bleak_cache=True)

    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_outer_cancel_without_subscription(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test outer cancel skips cleanup when no cancel handle was returned.

    Exercises the ``if cancel_connection_state is not None`` guard inside
    the outer ``await connected_future`` cancellation handler. When
    ``bluetooth_device_connect`` returns ``None`` (no subscription handle),
    ``self._cancel_connection_state`` stays ``None``; a real cancel of the
    awaiting task must not attempt to call a missing cancel callable.
    """
    bleak_client, client = bleak_pair

    with patch.object(
        client._client,
        "bluetooth_device_connect",
        return_value=None,
    ) as mock_connect:
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_connect.assert_called_once()
        assert client._cancel_connection_state is None
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    assert not client.is_connected
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
async def test_bleak_client_connect_outer_base_exception_cleans_up(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """A BaseException from the connection future still cleans up."""

    class ConnectBaseException(BaseException):
        """Sentinel exception that bypasses ``except Exception``."""

    bleak_client, client = bleak_pair
    original_create_future = client._loop.create_future
    captured: list[asyncio.Future[bool]] = []

    def capturing_create_future() -> asyncio.Future[bool]:
        fut = original_create_future()
        captured.append(fut)
        return fut

    mock_cancel_connection_state = Mock()
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=mock_cancel_connection_state,
        ) as mock_connect,
        patch.object(client._loop, "create_future", capturing_create_future),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_connect.assert_called_once()
        assert len(captured) == 1
        captured[0].set_exception(ConnectBaseException())
        with pytest.raises(ConnectBaseException):
            await task

    assert not client.is_connected
    mock_cancel_connection_state.assert_called_once_with()
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
async def test_bleak_client_connect_get_services_cleanup_shielded(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test the disconnect cleanup is shielded against re-cancellation.

    When ``_get_services`` raises ``CancelledError`` the connect path
    runs ``await self._disconnect()`` to release the BLE connection on
    the ESP side. ``_disconnect`` is itself a cancellation point, so a
    parent-task cancellation arriving while it is running would
    interrupt it half-way and leave the device connected on the ESP
    side. The fix wraps the disconnect in ``asyncio.shield`` and, on
    re-cancellation, finishes awaiting the disconnect before re-raising
    so the cleanup completes and the original cancellation still
    propagates to the caller.

    This test asserts both that ``CancelledError`` propagates and that
    the slow ``_disconnect`` ran to completion (its
    ``disconnect_finished`` event is set).
    """
    bleak_client, client = bleak_pair
    in_disconnect = asyncio.Event()
    release_disconnect = asyncio.Event()
    disconnect_finished = asyncio.Event()
    in_get_services = asyncio.Event()

    async def _hang_get_services(*args: Any, **kwargs: Any) -> Any:
        in_get_services.set()
        await asyncio.Event().wait()

    async def _slow_disconnect() -> bool:
        in_disconnect.set()
        await release_disconnect.wait()
        disconnect_finished.set()
        return True

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(client, "_get_services", side_effect=_hang_get_services),
        patch.object(client, "_disconnect", side_effect=_slow_disconnect),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        mock_connect.assert_called_once()
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        await in_get_services.wait()
        assert task.cancel() is True
        await in_disconnect.wait()
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        release_disconnect.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
        assert disconnect_finished.is_set()


@pytest.mark.asyncio
async def test_bleak_client_connect_get_services_failure_preserves_error(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    A cleanup-disconnect failure must not mask the original connect error.

    When ``_get_services`` raises after the link is up, ``connect`` runs
    ``await self._disconnect()`` to release the slot on the ESP side. If
    that cleanup disconnect itself fails, the original ``_get_services``
    error is the actionable one for the caller and retry logic — the
    disconnect failure must be suppressed, mirroring the ``CancelledError``
    cleanup branch. This asserts the surfaced ``BleakError`` carries the
    original failure, not the disconnect error.
    """
    _bleak_client, client = bleak_pair

    async def _boom_get_services(*args: Any, **kwargs: Any) -> Any:
        raise BleakError("original get_services failure")

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(client, "_get_services", side_effect=_boom_get_services),
        patch.object(
            client._client,
            "bluetooth_device_disconnect",
            side_effect=APIConnectionError("cleanup disconnect failed"),
        ),
    ):
        task = asyncio.create_task(
            client.connect(pair=False, dangerous_use_bleak_cache=True)
        )
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        with pytest.raises(BleakError) as exc_info:
            await task

    assert "original get_services failure" in str(exc_info.value)
    assert "cleanup disconnect failed" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_bleak_client_connect_wait_for_connection_slot(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test connect and disconnect when connection slots are not available."""
    bleak_client, client = make_bleak_client(client_data, free_slots=0)
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        mock_connect.assert_not_called()
        client._bluetooth_device.async_update_ble_connection_limits(10, 10, [])
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        await task

    assert client.is_connected
    assert client._mtu == 23
    with patch.object(
        client._client,
        "bluetooth_device_disconnect",
    ) as mock_disconnect:
        await client.disconnect()

    mock_disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bleak_client_connect_wait_for_connection_slot_timeout(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test connect and disconnect when connection slots wait times out."""
    bleak_client, client = make_bleak_client(client_data, free_slots=0)
    with (
        pytest.raises(asyncio.TimeoutError),
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
        patch("bleak_esphome.backend.client.CONNECT_FREE_SLOT_TIMEOUT", 0.0001),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        mock_connect.assert_not_called()
        await task

    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_with_pair_parameter(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test connect with pair=True calls pair method."""
    bleak_client, client = make_bleak_client(client_data, pair=True)
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
        patch.object(
            client,
            "_pair",
        ) as mock_pair,
    ):
        task = asyncio.create_task(bleak_client.connect())
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        await task

    assert client.is_connected
    mock_pair.assert_called_once()

    with patch.object(
        client._client,
        "bluetooth_device_disconnect",
    ) as mock_disconnect:
        await client.disconnect()

    mock_disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_esphome_client_connect_with_pair_false(
    esphome_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test connect with pair=False (default) does not log warning."""
    esphome_client._bluetooth_device.ble_connections_free = 10
    with (
        patch.object(
            esphome_client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            esphome_client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
    ):
        task = asyncio.create_task(esphome_client.connect(False))
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        callback(True, 23, 0)
        await task

    assert esphome_client.is_connected
    assert (
        "Explicit pairing during connect is not available in ESPHome" not in caplog.text
    )

    with patch.object(
        esphome_client._client,
        "bluetooth_device_disconnect",
    ) as mock_disconnect:
        await esphome_client.disconnect()

    mock_disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_pair_success(connected_client: ESPHomeClient) -> None:
    """Test successful pairing."""
    connected_client._feature_flags |= BluetoothProxyFeature.PAIRING.value

    with patch.object(
        connected_client._client,
        "bluetooth_device_pair",
        return_value=BluetoothDevicePairing(
            address=connected_client._address_as_int,
            paired=True,
            error=0,
        ),
    ) as mock_pair:
        await connected_client.pair()

    mock_pair.assert_called_once_with(connected_client._address_as_int)


@pytest.mark.asyncio
async def test_pair_failure(connected_client: ESPHomeClient) -> None:
    """Test pairing failure."""
    connected_client._feature_flags |= BluetoothProxyFeature.PAIRING.value

    with patch.object(
        connected_client._client,
        "bluetooth_device_pair",
        return_value=BluetoothDevicePairing(
            address=connected_client._address_as_int,
            paired=False,
            error=1,
        ),
    ):
        with pytest.raises(BleakError) as exc_info:
            await connected_client.pair()
        assert "Pairing failed due to error: 1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pair_not_connected(esphome_client: ESPHomeClient) -> None:
    """Test pairing when not connected."""
    esphome_client._feature_flags |= BluetoothProxyFeature.PAIRING.value

    with pytest.raises(BleakError) as exc_info:
        await esphome_client.pair()
    assert "is not connected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pair_feature_not_supported(connected_client: ESPHomeClient) -> None:
    """Test pairing when feature is not supported."""
    connected_client._feature_flags &= ~BluetoothProxyFeature.PAIRING.value

    with pytest.raises(NotImplementedError) as exc_info:
        await connected_client.pair()
    assert "Pairing is not available in this version ESPHome" in str(exc_info.value)
    assert connected_client._device_info.name in str(exc_info.value)


@pytest.mark.asyncio
async def test_unpair_success(connected_client: ESPHomeClient) -> None:
    """Test successful unpairing."""
    connected_client._feature_flags |= BluetoothProxyFeature.PAIRING.value

    with patch.object(
        connected_client._client,
        "bluetooth_device_unpair",
        return_value=BluetoothDeviceUnpairing(
            address=connected_client._address_as_int,
            success=True,
            error=0,
        ),
    ) as mock_unpair:
        await connected_client.unpair()

    mock_unpair.assert_called_once_with(connected_client._address_as_int)


@pytest.mark.asyncio
async def test_unpair_failure(connected_client: ESPHomeClient) -> None:
    """Test unpairing failure."""
    connected_client._feature_flags |= BluetoothProxyFeature.PAIRING.value

    with patch.object(
        connected_client._client,
        "bluetooth_device_unpair",
        return_value=BluetoothDeviceUnpairing(
            address=connected_client._address_as_int,
            success=False,
            error=2,
        ),
    ):
        with pytest.raises(BleakError) as exc_info:
            await connected_client.unpair()
        assert "Unpairing failed due to error: 2" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unpair_not_connected(esphome_client: ESPHomeClient) -> None:
    """Test unpairing when not connected."""
    esphome_client._feature_flags |= BluetoothProxyFeature.PAIRING.value

    with pytest.raises(BleakError) as exc_info:
        await esphome_client.unpair()
    assert "is not connected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_unpair_feature_not_supported(connected_client: ESPHomeClient) -> None:
    """Test unpairing when feature is not supported."""
    connected_client._feature_flags &= ~BluetoothProxyFeature.PAIRING.value

    with pytest.raises(NotImplementedError) as exc_info:
        await connected_client.unpair()
    assert "Unpairing is not available in this version ESPHome" in str(exc_info.value)
    assert connected_client._device_info.name in str(exc_info.value)


@pytest.mark.asyncio
async def test_start_notify_ccd_write_failure_cleans_up(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test that start_notify cleans up when CCD write fails."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(INDICATE_CHAR_UUID)
    assert char is not None
    assert "indicate" in char.properties

    mock_stop_notify = AsyncMock()
    mock_remove_callback = Mock()
    with (
        patch.object(
            connected_client._client,
            "bluetooth_gatt_start_notify",
            return_value=(mock_stop_notify, mock_remove_callback),
        ),
        patch.object(
            connected_client._client,
            "bluetooth_gatt_write_descriptor",
            side_effect=Exception("CCD write failed"),
        ),
        patch.object(
            connected_client._client,
            "bluetooth_gatt_stop_notify",
        ) as mock_stop,
        pytest.raises(Exception, match="CCD write failed"),
    ):
        await connected_client.start_notify(char, lambda data: None)

    mock_stop.assert_called_once_with(connected_client._address_as_int, char.handle)
    assert char.handle not in connected_client._notify_cancels


@pytest.mark.asyncio
async def test_start_notify_ccd_write_cancelled_cleans_up(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test that start_notify cleans up when CCD write is cancelled."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(INDICATE_CHAR_UUID)
    assert char is not None

    mock_stop_notify = AsyncMock()
    mock_remove_callback = Mock()
    with (
        patch.object(
            connected_client._client,
            "bluetooth_gatt_start_notify",
            return_value=(mock_stop_notify, mock_remove_callback),
        ),
        patch.object(
            connected_client._client,
            "bluetooth_gatt_write_descriptor",
            side_effect=asyncio.CancelledError(),
        ),
        patch.object(
            connected_client._client,
            "bluetooth_gatt_stop_notify",
        ) as mock_stop,
        pytest.raises(asyncio.CancelledError),
    ):
        await connected_client.start_notify(char, lambda data: None)

    mock_stop.assert_called_once_with(connected_client._address_as_int, char.handle)
    assert char.handle not in connected_client._notify_cancels


@pytest.mark.asyncio
async def test_start_notify_success_with_ccd_write(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test that start_notify succeeds and writes to CCD."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(INDICATE_CHAR_UUID)
    assert char is not None
    cccd = char.get_descriptor(CCCD_UUID)
    assert cccd is not None

    mock_stop_notify = AsyncMock()
    mock_remove_callback = Mock()
    with (
        patch.object(
            connected_client._client,
            "bluetooth_gatt_start_notify",
            return_value=(mock_stop_notify, mock_remove_callback),
        ),
        patch.object(
            connected_client._client,
            "bluetooth_gatt_write_descriptor",
        ) as mock_write_descriptor,
    ):
        await connected_client.start_notify(char, lambda data: None)

    mock_write_descriptor.assert_called_once_with(
        connected_client._address_as_int,
        cccd.handle,
        b"\x02\x00",
    )
    assert char.handle in connected_client._notify_cancels


@pytest.mark.asyncio
async def test_start_notify_missing_cccd_raises_error(
    connected_client: ESPHomeClient,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test that start_notify raises error when characteristic has no CCCD."""
    services = await fetch_services(connected_client, esphome_bluetooth_gatt_services)
    char = services.get_characteristic(INDICATE_CHAR_UUID)
    assert char is not None
    assert "indicate" in char.properties

    mock_stop_notify = AsyncMock()
    mock_remove_callback = Mock()
    with (
        patch.object(
            connected_client._client,
            "bluetooth_gatt_start_notify",
            return_value=(mock_stop_notify, mock_remove_callback),
        ),
        patch.object(char, "get_descriptor", return_value=None),
        patch.object(
            connected_client._client,
            "bluetooth_gatt_stop_notify",
        ) as mock_stop,
        pytest.raises(BleakError, match="does not have a characteristic client config"),
    ):
        await connected_client.start_notify(char, lambda data: None)

    mock_stop.assert_called_once_with(connected_client._address_as_int, char.handle)


@pytest.mark.asyncio
async def test_set_connection_params(connected_client: ESPHomeClient) -> None:
    """Test that set_connection_params calls through to the API client."""
    connected_client._feature_flags |= (
        BluetoothProxyFeature.CONNECTION_PARAMS_SETTING.value
    )

    with patch.object(
        connected_client._client,
        "bluetooth_device_set_connection_params",
    ) as mock_set_params:
        await connected_client.set_connection_params(800, 800, 0, 300)

    mock_set_params.assert_called_once_with(
        connected_client._address_as_int, 800, 800, 0, 300
    )


@pytest.mark.asyncio
async def test_set_connection_params_not_supported(
    connected_client: ESPHomeClient,
) -> None:
    """Test that set_connection_params returns early when flag is not set."""
    # The default client_data fixture does NOT include CONNECTION_PARAMS_SETTING.
    with patch.object(
        connected_client._client,
        "bluetooth_device_set_connection_params",
    ) as mock_set_params:
        await connected_client.set_connection_params(800, 800, 0, 300)

    mock_set_params.assert_not_called()


@pytest.mark.asyncio
async def test_set_connection_params_not_connected(
    esphome_client: ESPHomeClient,
) -> None:
    """Test that set_connection_params raises BleakError when not connected."""
    esphome_client._feature_flags |= (
        BluetoothProxyFeature.CONNECTION_PARAMS_SETTING.value
    )

    with pytest.raises(BleakError) as exc_info:
        await esphome_client.set_connection_params(800, 800, 0, 300)
    assert "is not connected" in str(exc_info.value)
