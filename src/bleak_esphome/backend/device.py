"""Bluetooth device models for esphome."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from bleak_retry_connector import Allocations
from bluetooth_data_tools import int_to_bluetooth_address

from .cache import ESPHomeBluetoothCache

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ESPHomeBluetoothDevice:
    """Bluetooth data for a specific ESPHome device."""

    name: str
    mac_address: str
    ble_connections_free: int = 0
    ble_connections_limit: int = 0
    ble_allocations: list[int] = field(default_factory=list)
    _ble_connection_free_futures: list[asyncio.Future[int]] = field(
        default_factory=list
    )
    loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_running_loop)
    available: bool = False
    cache: ESPHomeBluetoothCache = field(default_factory=ESPHomeBluetoothCache)
    _connection_slots_callback: Callable[[Allocations], None] | None = None
    _called_callback: bool = False

    def async_subscribe_connection_slots(
        self, callback: Callable[[Allocations], None]
    ) -> None:
        """Subscribe to connection slot changes."""
        self._connection_slots_callback = callback
        self._called_callback = False

    def async_update_ble_connection_limits(
        self, free: int, limit: int, allocated: list[int]
    ) -> None:
        """Update the BLE connection limits."""
        _LOGGER.debug(
            "%s [%s]: BLE connection limits: used=%s free=%s limit=%s allocated=%s",
            self.name,
            self.mac_address,
            limit - free,
            free,
            limit,
            allocated,
        )
        changed = (
            free != self.ble_connections_free
            or limit != self.ble_connections_limit
            or allocated != self.ble_allocations
        )
        self.ble_connections_free = free
        self.ble_connections_limit = limit
        self.ble_allocations = allocated
        if free:
            for fut in self._ble_connection_free_futures:
                # If wait_for_ble_connections_free gets cancelled, it will
                # leave a future in the list. We need to check if it's done
                # before setting the result.
                if not fut.done():
                    fut.set_result(free)
            self._ble_connection_free_futures.clear()
        if (changed or not self._called_callback) and (
            connection_slots_callback := self._connection_slots_callback
        ):
            # Currently we don't know which connections are in use, so we
            # just return an empty list.
            self._called_callback = True
            connection_slots_callback(
                Allocations(
                    self.mac_address,
                    limit,
                    free,
                    [int_to_bluetooth_address(address) for address in allocated],
                )
            )

    def _wait_for_ble_connections_free_timeout(self, fut: asyncio.Future[int]) -> None:
        """Timeout the wait_for_ble_connections_free future."""
        fut.set_exception(asyncio.TimeoutError())

    async def wait_for_ble_connections_free(self, timeout: float) -> int:
        """Wait until there are free BLE connections."""
        if self.ble_connections_free > 0:
            return self.ble_connections_free
        fut: asyncio.Future[int] = self.loop.create_future()
        self._ble_connection_free_futures.append(fut)
        cancel_timeout = self.loop.call_later(
            timeout, self._wait_for_ble_connections_free_timeout, fut
        )
        try:
            return await fut
        finally:
            cancel_timeout.cancel()
