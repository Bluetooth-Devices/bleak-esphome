"""Tests for ESPHomeBluetoothDevice."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from bleak_retry_connector import Allocations

from bleak_esphome.backend.device import ESPHomeBluetoothDevice

from ._helpers import ESP_MAC_ADDRESS


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_returns_immediately_when_free(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Return current count without suspending when a slot is already free."""
    bluetooth_device.ble_connections_free = 3
    assert await bluetooth_device.wait_for_ble_connections_free(1.0) == 3


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_resolves_on_update(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Suspended waiter wakes when the update reports a free slot."""
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(1.0))
    await asyncio.sleep(0)
    assert not task.done()
    bluetooth_device.async_update_ble_connection_limits(2, 5, [10, 20, 30])
    assert await task == 2
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_timeout(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Waiting with no available slot raises ``TimeoutError`` after deadline."""
    bluetooth_device.ble_connections_limit = 3
    bluetooth_device.ble_connections_free = 0
    with pytest.raises(TimeoutError) as exc_info:
        await bluetooth_device.wait_for_ble_connections_free(0.001)
    # The timeout must name the saturated proxy and its slot state so the
    # failure is actionable rather than an anonymous timeout.
    message = str(exc_info.value)
    assert "proxy" in message
    assert "AA:BB:CC:DD:EE:FF" in message
    assert "limit=3" in message
    assert "in use=3" in message
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_cancellation_cleans_up(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Cancelling the waiter must remove the pending future from the list."""
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(10.0))
    await asyncio.sleep(0)
    assert len(bluetooth_device._ble_connection_free_futures) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_timer_after_result_does_not_raise(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Late-firing timeout must not raise on an already-resolved future."""
    fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    fut.set_result(1)
    bluetooth_device._wait_for_ble_connections_free_timeout(fut)
    assert fut.result() == 1


@pytest.mark.asyncio
async def test_async_update_ble_connection_limits_skips_done_futures(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A future already resolved (e.g. cancelled) is skipped on update."""
    done_fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    done_fut.cancel()
    pending_fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    bluetooth_device._ble_connection_free_futures.update([done_fut, pending_fut])
    bluetooth_device.async_update_ble_connection_limits(4, 4, [])
    assert pending_fut.done()
    assert pending_fut.result() == 4
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_subscribe_connection_slots_fires_on_first_update(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """First update always invokes the callback even when values unchanged."""
    callback = Mock()
    bluetooth_device.async_subscribe_connection_slots(callback)
    bluetooth_device.async_update_ble_connection_limits(0, 0, [])
    callback.assert_called_once()
    allocation = callback.call_args[0][0]
    assert isinstance(allocation, Allocations)
    assert allocation.adapter == ESP_MAC_ADDRESS
    assert allocation.slots == 0
    assert allocation.free == 0
    assert allocation.allocated == []


@pytest.mark.asyncio
async def test_subscribe_connection_slots_skips_when_unchanged(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Repeat updates with identical values do not refire the callback."""
    callback = Mock()
    bluetooth_device.async_subscribe_connection_slots(callback)
    bluetooth_device.async_update_ble_connection_limits(1, 2, [42])
    bluetooth_device.async_update_ble_connection_limits(1, 2, [42])
    assert callback.call_count == 1


@pytest.mark.asyncio
async def test_subscribe_connection_slots_fires_on_change(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Each distinct update triggers the subscriber callback."""
    callback = Mock()
    bluetooth_device.async_subscribe_connection_slots(callback)
    bluetooth_device.async_update_ble_connection_limits(0, 2, [])
    bluetooth_device.async_update_ble_connection_limits(1, 2, [99])
    bluetooth_device.async_update_ble_connection_limits(2, 2, [])
    assert callback.call_count == 3
    third = callback.call_args_list[2][0][0]
    assert third.free == 2
    assert third.slots == 2
    assert third.allocated == []
