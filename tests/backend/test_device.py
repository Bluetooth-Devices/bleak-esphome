"""Tests for ESPHomeBluetoothDevice."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from bleak_retry_connector import Allocations

from bleak_esphome.backend.device import ESPHomeBluetoothDevice

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_returns_immediately_when_free() -> None:
    """Return current count without suspending when a slot is already free."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_free = 3
    assert await device.wait_for_ble_connections_free(1.0) == 3


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_resolves_on_update() -> None:
    """A suspended waiter wakes when ``async_update_ble_connection_limits`` reports a slot."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    task = asyncio.create_task(device.wait_for_ble_connections_free(1.0))
    await asyncio.sleep(0)
    assert not task.done()
    device.async_update_ble_connection_limits(2, 5, [10, 20, 30])
    assert await task == 2
    assert device._ble_connection_free_futures == []


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_timeout() -> None:
    """Waiting with no available slot raises ``TimeoutError`` after the deadline."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    with pytest.raises(TimeoutError):
        await device.wait_for_ble_connections_free(0.001)
    # Future must be cleaned up so the internal list does not grow forever.
    assert device._ble_connection_free_futures == []


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_cancellation_cleans_up() -> None:
    """Cancelling the waiter must remove the pending future from the list."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    task = asyncio.create_task(device.wait_for_ble_connections_free(10.0))
    await asyncio.sleep(0)
    assert len(device._ble_connection_free_futures) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert device._ble_connection_free_futures == []


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_timer_after_result_does_not_raise() -> (
    None
):
    """A late-firing timeout must not raise ``InvalidStateError`` on a resolved future."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    fut.set_result(1)
    # Simulate the timer running after the future has already been resolved.
    device._wait_for_ble_connections_free_timeout(fut)
    assert fut.result() == 1


@pytest.mark.asyncio
async def test_async_update_ble_connection_limits_skips_done_futures() -> None:
    """A future already resolved (e.g. cancelled) is skipped on update."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    done_fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    done_fut.cancel()
    pending_fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    device._ble_connection_free_futures.extend([done_fut, pending_fut])
    device.async_update_ble_connection_limits(4, 4, [])
    assert pending_fut.done()
    assert pending_fut.result() == 4
    # Both must be cleared.
    assert device._ble_connection_free_futures == []


@pytest.mark.asyncio
async def test_subscribe_connection_slots_fires_on_first_update() -> None:
    """First update always invokes the callback even if values were unchanged from defaults."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    callback = Mock()
    device.async_subscribe_connection_slots(callback)
    device.async_update_ble_connection_limits(0, 0, [])
    callback.assert_called_once()
    allocation = callback.call_args[0][0]
    assert isinstance(allocation, Allocations)
    assert allocation.adapter == ESP_MAC_ADDRESS
    assert allocation.slots == 0
    assert allocation.free == 0
    assert allocation.allocated == []


@pytest.mark.asyncio
async def test_subscribe_connection_slots_skips_when_unchanged() -> None:
    """Repeat updates with identical values do not refire the callback."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    callback = Mock()
    device.async_subscribe_connection_slots(callback)
    device.async_update_ble_connection_limits(1, 2, [42])
    device.async_update_ble_connection_limits(1, 2, [42])
    assert callback.call_count == 1


@pytest.mark.asyncio
async def test_subscribe_connection_slots_fires_on_change() -> None:
    """Each distinct update triggers the subscriber callback."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    callback = Mock()
    device.async_subscribe_connection_slots(callback)
    device.async_update_ble_connection_limits(0, 2, [])
    device.async_update_ble_connection_limits(1, 2, [99])
    device.async_update_ble_connection_limits(2, 2, [])
    assert callback.call_count == 3
    third = callback.call_args_list[2][0][0]
    assert third.free == 2
    assert third.slots == 2
    assert third.allocated == []
