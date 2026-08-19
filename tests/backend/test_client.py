import asyncio
import contextlib
import inspect
import logging
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
    CONNECT_FREE_SLOT_TIMEOUT,
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
    patch_connect_rpcs,
    patch_get_services,
    start_connect,
)

PRIMARY_CHAR_UUID = "090b7847-e12b-09a8-b04b-8e0922a9abab"
INDICATE_CHAR_UUID = "00002a05-0000-1000-8000-00805f9b34fb"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"
BLE_ADDRESS_AS_INT = 225106397622015


class _Signal(BaseException):
    """Stand-in for KeyboardInterrupt that pytest does not intercept."""


async def _boom_get_services(*args: Any, **kwargs: Any) -> Any:
    """Fail service discovery with a retryable error."""
    raise BleakError("services boom")


def _capture_created_futures(
    client: ESPHomeClient,
) -> tuple[list["asyncio.Future[bool]"], Any]:
    """Return a capture list and a create_future replacement to patch in."""
    captured: list[asyncio.Future[bool]] = []
    original_create_future = client._loop.create_future

    def capturing_create_future() -> asyncio.Future[bool]:
        fut = original_create_future()
        captured.append(fut)
        return fut

    return captured, capturing_create_future


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

    # The public path awaits the confirmation with aioesphomeapi's
    # default timeout; cleanup paths use the synchronous no-wait helper.
    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)


@pytest.mark.asyncio
async def test_bleak_client_reconciled_when_missing_from_allocations(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """
    Test a connected client is torn down when the proxy no longer lists it.

    Covers the phantom-connection heal: the ``connected=false``
    notification was lost, so only the allocated list reveals the loss.
    """
    bleak_client, client = bleak_pair
    bluetooth_device = client._bluetooth_device
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

    assert client._is_connected
    disconnected_callback = Mock()
    client._disconnected_callback = disconnected_callback

    # A trusted update that still lists the client leaves it connected.
    bluetooth_device.async_update_ble_connection_limits(1, 2, [BLE_ADDRESS_AS_INT])
    assert client._is_connected
    disconnected_callback.assert_not_called()

    # The proxy reports the address gone: the client must be torn down.
    bluetooth_device.async_update_ble_connection_limits(2, 2, [])
    assert not client.is_connected
    disconnected_callback.assert_called_once_with()
    assert client._async_esp_disconnected not in client._disconnect_callbacks


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
    captured, capturing_create_future = _capture_created_futures(client)

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
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=mock_cancel_connection_state,
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

        assert not client.is_connected
        mock_cancel_connection_state.assert_called_once_with()
        assert client._cancel_connection_state is None

        # A late ``connected=True`` for the abandoned attempt must not
        # resurrect state and must release the link the ESP just
        # established.
        callback(True, 23, 0)
        assert not client.is_connected
        assert client._async_esp_disconnected not in client._disconnect_callbacks

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)


@pytest.mark.asyncio
async def test_bleak_client_connect_cancel_racing_link_up_releases(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a link up racing a real cancel is released by the abandonment.

    ``task.cancel()`` cancels ``connected_future`` synchronously; if the
    ESP's ``connected=True`` then arrives before the task resumes, the
    attempt's subscription is still installed, so the callback defers to
    the unwinding attempt's abandonment, which must release the link
    rather than treating the attempt as never having connected.
    """
    bleak_client, client = bleak_pair
    with patch_connect_rpcs(client) as (mock_connect, mock_disconnect):
        task, callback = await start_connect(bleak_client, mock_connect)
        assert task.cancel() is True
        # The future is already cancelled; the link comes up before the
        # task resumes.
        callback(True, 23, 0)
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
    assert not client.is_connected
    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)


@pytest.mark.asyncio
async def test_bleak_client_connect_settle_runs_with_scanning_resumed(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test the settle runs outside the scanner's connecting pause.

    The release is already sent by then, so a saturated proxy must not
    have its scanner blanked for up to the settle timeout as well.
    """
    bleak_client, client = bleak_pair
    scanning_during_settle: list[bool] = []

    async def _record_scanning(context: str) -> None:
        scanning_during_settle.append(client._scanner.scanning)

    with (
        patch_connect_rpcs(client) as (mock_connect, _mock_disconnect),
        patch.object(
            client, "_settle_slot_after_failure", side_effect=_record_scanning
        ),
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 1)
        with pytest.raises(BleakError, match="while connecting"):
            await task

    assert scanning_during_settle == [True]


@pytest.mark.asyncio
async def test_bleak_client_connect_failed_release_skips_settle(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a failed release send skips the settle.

    If the disconnect request never went out (a dead API connection above
    all), the free count can never update over that same connection;
    settling would stall the full timeout with scanning paused.
    """
    bleak_client, client = bleak_pair
    with (
        patch_connect_rpcs(
            client, disconnect_side_effect=APIConnectionError("api gone")
        ) as (mock_connect, _mock_disconnect),
        patch.object(client, "_settle_slot_after_failure") as mock_settle,
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 1)
        with pytest.raises(BleakError, match="while connecting"):
            await task

    mock_settle.assert_not_awaited()


@pytest.mark.asyncio
async def test_bleak_client_connect_settle_defect_logged_as_warning(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test an unexpected settle error surfaces as a warning.

    A TimeoutError is the expected slow proxy shape and stays at debug;
    anything else is a defect in the wait path and must not hide there.
    """
    bleak_client, client = bleak_pair
    with (
        patch_connect_rpcs(client) as (mock_connect, _mock_disconnect),
        patch.object(
            client,
            "_wait_for_free_connection_slot",
            side_effect=[None, RuntimeError("wait path defect")],
        ),
        caplog.at_level(logging.WARNING),
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 1)
        with pytest.raises(BleakError, match="while connecting"):
            await task

    assert "Unexpected error while waiting for the slot to settle" in caplog.text


@pytest.mark.asyncio
async def test_bleak_client_connect_services_drop_skips_settle(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a link dropped during discovery releases nothing and skips settle.

    When the device disconnects mid ``_get_services`` the local state is
    already torn down; the attempt no longer holds a slot, so there is
    nothing to release and nothing to settle for.
    """
    bleak_client, client = bleak_pair

    async def _drop_then_boom(*args: Any, **kwargs: Any) -> Any:
        client._async_ble_device_disconnected()
        raise BleakError("dropped during discovery")

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(client, "_get_services", side_effect=_drop_then_boom),
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
        patch.object(client, "_settle_slot_after_failure") as mock_settle,
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 0)
        with pytest.raises(BleakError, match="dropped during discovery"):
            await task

    mock_disconnect.assert_not_called()
    mock_settle.assert_not_awaited()
    assert not client.is_connected


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_shape", ["error_code", "pair", "services"])
async def test_bleak_client_abandoned_attempt_preserves_disconnected_callback(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
    failure_shape: str,
) -> None:
    """
    Test abandonment is silent to the consumer and the callback survives.

    An abandoned attempt never handed the consumer a connected client, so
    it must not fire ``disconnected_callback`` and must not null it; the
    retry connector reuses one client instance, and a later successful
    connect still has to deliver the real disconnect notification. Pinned
    for every abandonment shape: a connect error after link up, a failed
    pairing, and a failed service discovery.
    """
    bleak_client, client = bleak_pair
    disconnected_callback = Mock()
    client._disconnected_callback = disconnected_callback

    with (
        patch_connect_rpcs(client) as (mock_connect, _mock_disconnect),
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
    ):
        # The failure injections live in their own scope so attempt 2
        # runs without them.
        with contextlib.ExitStack() as failure_stack:
            pair = False
            if failure_shape == "pair":
                pair = True
                failure_stack.enter_context(
                    patch.object(
                        client._client,
                        "bluetooth_device_pair",
                        return_value=BluetoothDevicePairing(
                            address=client._address_as_int, paired=False, error=1
                        ),
                    )
                )
            if failure_shape == "services":
                failure_stack.enter_context(
                    patch.object(
                        client, "_get_services", side_effect=_boom_get_services
                    )
                )
            # Attempt 1 fails; the consumer never saw a connected client.
            task, callback = await start_connect(client, mock_connect, pair=pair)
            callback(True, 23, 1 if failure_shape == "error_code" else 0)
            with pytest.raises(BleakError):
                await task
            disconnected_callback.assert_not_called()
            assert client._disconnected_callback is disconnected_callback

        # Attempt 2 succeeds on the same instance.
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 0)
        await task
        assert client.is_connected

        # The real disconnect still notifies the consumer exactly once.
        callback(False, 23, 0)
        disconnected_callback.assert_called_once_with()


@pytest.mark.asyncio
async def test_bleak_client_connect_error_without_link_cleans_up_locally(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a connect error with no link up skips the release.

    A ``connected=False`` error resolution means the ESP holds nothing;
    only the local cleanup runs, no disconnect is sent, and the settle
    is skipped since the attempt never held a slot.
    """
    bleak_client, client = bleak_pair
    with patch_connect_rpcs(client) as (mock_connect, mock_disconnect):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(False, 23, 1)
        with pytest.raises(BleakError, match="while connecting"):
            await task

    mock_disconnect.assert_not_called()
    assert not client.is_connected
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
async def test_bleak_client_connect_base_exception_releases_without_settle(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a BaseException from the wait releases without settling.

    A real signal (a ``BaseException`` such as ``KeyboardInterrupt``
    delivered at the await) must not be stalled behind the slot settle;
    the link is still released so the proxy slot is not leaked.
    """
    bleak_client, client = bleak_pair
    captured, capturing_create_future = _capture_created_futures(client)

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
        patch.object(client._loop, "create_future", capturing_create_future),
        patch.object(client, "_wait_for_free_connection_slot") as mock_settle,
    ):
        task, _callback = await start_connect(bleak_client, mock_connect)
        # Simulate the link coming up while a signal lands at the await.
        client._is_connected = True
        captured[0].set_exception(_Signal())
        with pytest.raises(_Signal):
            await task

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert not client.is_connected
    # No settle on the signal path; only the entry gate call happened.
    assert mock_settle.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [0, 1])
async def test_bleak_client_connect_cancel_after_link_up_disconnects_esp(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    error: int,
) -> None:
    """
    Test cancellation delivered after the link already came up.

    If the awaiting task is cancelled after the connection-state callback
    reported ``connected=True`` (asyncio still delivers ``CancelledError``
    at the ``await`` even though the future holds a result), the ESP side
    holds a live connection that no client owns. ``connect()`` must release
    it with the synchronous no-wait disconnect so the proxy's slot is not
    leaked, clean up local state, and still propagate the cancellation.
    The ``error=1`` case additionally pins that a stored future error is
    retrieved rather than left to warn at garbage collection.
    """
    bleak_client, client = bleak_pair
    mock_cancel_connection_state = Mock()
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=mock_cancel_connection_state,
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, error)
        assert client._is_connected
        # Cancel before the awaiting task resumes: the future already has a
        # result, but Task._must_cancel still raises CancelledError at the
        # await point.
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert not client.is_connected
    mock_cancel_connection_state.assert_called_once_with()
    assert client._cancel_connection_state is None
    assert client._async_esp_disconnected not in client._disconnect_callbacks


@pytest.mark.asyncio
async def test_bleak_client_connect_error_after_link_up_disconnects_esp(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a ``connected=True`` state with an error code releases the link.

    When the connection-state callback reports connected with an error,
    the future fails while ``_is_connected`` is already set; the ESP side
    may hold a live connection, so ``connect()`` must release it instead
    of leaking the proxy's slot.
    """
    bleak_client, client = bleak_pair
    with patch_connect_rpcs(client) as (mock_connect, mock_disconnect):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 1)
        with pytest.raises(BleakError, match="while connecting"):
            await task

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert not client.is_connected
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("release_error", "expected_level", "expected_text"),
    [
        (
            RuntimeError("boom"),
            logging.WARNING,
            "Failed to release ESP-side connection",
        ),
        (
            APIConnectionError("api gone"),
            logging.DEBUG,
            "API connection gone, ESP-side release skipped",
        ),
    ],
)
async def test_bleak_client_connect_cancel_after_link_up_disconnect_failure_logged(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    caplog: pytest.LogCaptureFixture,
    release_error: Exception,
    expected_level: int,
    expected_text: str,
) -> None:
    """
    Test a failing release does not mask the cancellation.

    If the ESP-side release fails while cleaning up a cancelled connect,
    the cancellation still propagates to the caller. A generic failure is
    a leaked proxy slot and warns; a dead API connection is not a leak
    (the proxy tears its links down once the subscriber is gone) and only
    logs at debug so operators are not misdirected during a reconnect.
    """
    bleak_client, client = bleak_pair
    with (
        patch_connect_rpcs(client, disconnect_side_effect=release_error) as (
            mock_connect,
            mock_disconnect,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 0)
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert not client.is_connected
    matching = [record for record in caplog.records if expected_text in record.message]
    assert len(matching) == 1
    assert matching[0].levelno == expected_level


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

    Exercises the ``if connected_future.done():`` arm inside the
    ``except Exception`` handler around the ``bluetooth_device_connect``
    call. The callback reports a failed connection (which sets a
    ``BleakError`` on ``connected_future``), then ``bluetooth_device_connect``
    itself raises. The stored error is retrieved via
    ``_retrieve_future_error`` and the original exception propagates.
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
async def test_bleak_client_connect_inner_cancelled_retrieves_resolved_future_error(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test the inner cancel handler retrieves an already-stored error.

    If ``bluetooth_device_connect`` raises ``CancelledError`` after the
    connection-state callback already resolved ``connected_future`` with
    an error, ``_retrieve_future_error`` marks it retrieved so asyncio
    does not warn about it, and the cancellation handling proceeds.
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
    Test outer cancellation before the subscription handle was stored.

    The cleanup path funnels through ``_async_disconnected_cleanup``,
    which tolerates ``_cancel_connection_state`` still being ``None``.
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
async def test_bleak_client_connect_rpc_signal_cleans_up(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a signal raised by the connect RPC itself still tears down.

    aioesphomeapi releases the ESP side in its own failure handlers; the
    local abandonment must still run so the subscription and state do
    not leak.
    """
    bleak_client, client = bleak_pair
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            side_effect=_Signal,
        ),
        pytest.raises(_Signal),
    ):
        await bleak_client.connect(dangerous_use_bleak_cache=True)

    assert not client.is_connected
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
async def test_bleak_client_connect_outer_base_exception_cleans_up(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """A BaseException from the connection future still cleans up."""
    bleak_client, client = bleak_pair
    captured, capturing_create_future = _capture_created_futures(client)

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
        captured[0].set_exception(_Signal())
        with pytest.raises(_Signal):
            await task

    assert not client.is_connected
    mock_cancel_connection_state.assert_called_once_with()
    assert client._cancel_connection_state is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("services_boom", "expected_error", "expected_log"),
    [
        (False, "while connecting", "failed connect"),
        (True, "services boom", "failed connect setup"),
    ],
)
async def test_bleak_client_connect_failure_logs_settle_timeout(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
    caplog: pytest.LogCaptureFixture,
    services_boom: bool,
    expected_error: str,
    expected_log: str,
) -> None:
    """
    Test a slot that never settles after a failed attempt is logged.

    Covers both failure shapes that settle before the retry: a connect
    error after the link came up and a service discovery failure. The
    settle timeout must not mask the original error, but it is the
    direct cause of the next retry's entry gate failing, so it is
    logged rather than dropped.
    """
    bleak_client, client = bleak_pair

    with (
        patch_connect_rpcs(client) as (mock_connect, _mock_disconnect),
        patch.object(
            client,
            "_wait_for_free_connection_slot",
            # First call is the connect entry gate; the second is the
            # settle after the release, which times out.
            side_effect=[None, TimeoutError("no slot")],
        ) as mock_wait,
        contextlib.ExitStack() as failure_stack,
        caplog.at_level(logging.DEBUG),
    ):
        if services_boom:
            failure_stack.enter_context(
                patch.object(client, "_get_services", side_effect=_boom_get_services)
            )
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 0 if services_boom else 1)
        with pytest.raises(BleakError, match=expected_error):
            await task

    assert f"Slot did not settle after {expected_log}" in caplog.text
    # The settle is capped to the same window as the next attempt's
    # entry gate; a longer budget only delays surfacing the error.
    assert mock_wait.call_args_list[-1][0] == (CONNECT_FREE_SLOT_TIMEOUT,)


@pytest.mark.asyncio
async def test_bleak_client_connect_get_services_signal_releases_without_settle(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a signal during service discovery releases without settling.

    A ``BaseException`` from the post-connect setup must not be stalled
    behind the slot settle; the link is still released.
    """
    bleak_client, client = bleak_pair

    async def _boom_signal_get_services(*args: Any, **kwargs: Any) -> Any:
        raise _Signal

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(client, "_get_services", side_effect=_boom_signal_get_services),
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
        patch.object(client, "_settle_slot_after_failure") as mock_settle,
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 0)
        with pytest.raises(_Signal):
            await task

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    mock_settle.assert_not_awaited()
    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_get_services_cancel_releases_link(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    Test a cancel during service discovery releases the ESP-side link.

    The release is synchronous, so the cancellation is neither delayed
    nor absorbed; it propagates immediately after the release is sent.
    """
    bleak_client, client = bleak_pair
    in_get_services = asyncio.Event()

    async def _hang_get_services(*args: Any, **kwargs: Any) -> Any:
        in_get_services.set()
        await asyncio.Event().wait()

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(client, "_get_services", side_effect=_hang_get_services),
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
    ):
        task, callback = await start_connect(bleak_client, mock_connect)
        callback(True, 23, 0)
        await in_get_services.wait()
        assert task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_get_services_failure_preserves_error(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    A cleanup-disconnect failure must not mask the original connect error.

    When ``_get_services`` raises after the link is up, ``connect`` runs
    the synchronous release to free the slot on the ESP side. If that
    release itself fails, the original ``_get_services`` error is the
    actionable one for the caller and retry logic — the release failure
    is logged, not raised. This asserts the release was attempted and the
    surfaced ``BleakError`` carries the original failure.
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
            "bluetooth_device_disconnect_no_wait",
            side_effect=RuntimeError("cleanup disconnect failed"),
        ) as mock_disconnect,
    ):
        task, callback = await start_connect(client, mock_connect, pair=False)
        callback(True, 23, 0)
        with pytest.raises(BleakError) as exc_info:
            await task

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert "original get_services failure" in str(exc_info.value)
    assert "cleanup disconnect failed" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_bleak_client_connect_pair_failure_releases_slot(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    A pairing failure during ``connect(pair=True)`` must release the link.

    The pairing step runs after the GATT link is established. If it fails,
    ``connect`` must still disconnect on the ESP side so the connection slot
    is not leaked, mirroring the ``_get_services`` cleanup path. This asserts
    the pairing ``BleakError`` propagates and that a cleanup disconnect ran.
    """
    _bleak_client, client = bleak_pair

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_device_pair",
            return_value=BluetoothDevicePairing(
                address=client._address_as_int,
                paired=False,
                error=1,
            ),
        ),
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
        ) as mock_disconnect,
    ):
        task, callback = await start_connect(client, mock_connect, pair=True)
        callback(True, 23, 0)
        with pytest.raises(BleakError, match="Pairing failed"):
            await task

    mock_disconnect.assert_called_once()
    assert not client.is_connected


@pytest.mark.asyncio
async def test_bleak_client_connect_pair_failure_preserves_error(
    bleak_pair: tuple[BleakClient, ESPHomeClient],
) -> None:
    """
    A cleanup-disconnect failure must not mask the original pairing error.

    When pairing fails after the link is up, ``connect`` runs the
    synchronous release to free the slot. If that release itself fails,
    the original pairing error is the actionable one for the caller — the
    release failure is logged, not raised, mirroring the ``_get_services``
    cleanup branch.
    """
    _bleak_client, client = bleak_pair

    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
            return_value=Mock(),
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_device_pair",
            return_value=BluetoothDevicePairing(
                address=client._address_as_int,
                paired=False,
                error=1,
            ),
        ),
        patch.object(
            client._client,
            "bluetooth_device_disconnect_no_wait",
            side_effect=RuntimeError("cleanup disconnect failed"),
        ) as mock_disconnect,
    ):
        task, callback = await start_connect(client, mock_connect, pair=True)
        callback(True, 23, 0)
        with pytest.raises(BleakError) as exc_info:
            await task

    mock_disconnect.assert_called_once_with(BLE_ADDRESS_AS_INT)
    assert "Pairing failed" in str(exc_info.value)
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
