"""Bluetooth device models for esphome."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bleak_retry_connector import Allocations
from bluetooth_data_tools import int_to_bluetooth_address

from .cache import ESPHomeBluetoothCache

if TYPE_CHECKING:
    from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ESPHomeBluetoothDevice:
    """Bluetooth data for a specific ESPHome device."""

    name: str
    mac_address: str
    ble_connections_free: int = 0
    ble_connections_limit: int = 0
    ble_allocations: list[int] = field(default_factory=list)
    _ble_connection_free_futures: set[asyncio.Future[int]] = field(default_factory=set)
    loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_running_loop)
    available: bool = False
    cache: ESPHomeBluetoothCache = field(default_factory=ESPHomeBluetoothCache)
    _connection_slots_callback: Callable[[Allocations], None] | None = None
    _called_callback: bool = False
    _tracked_clients: dict[int, Callable[[], None]] = field(default_factory=dict)

    def async_subscribe_connection_slots(
        self, callback: Callable[[Allocations], None]
    ) -> None:
        """Subscribe to connection slot changes."""
        self._connection_slots_callback = callback
        self._called_callback = False

    def async_track_client(
        self, address: int, on_ble_disconnected: Callable[[], None]
    ) -> None:
        """
        Track a connected client so it can be reconciled against allocations.

        ``on_ble_disconnected`` is invoked when the proxy's authoritative
        allocated list no longer contains ``address``.
        """
        self._tracked_clients[address] = on_ble_disconnected

    def async_untrack_client(
        self, address: int, on_ble_disconnected: Callable[[], None]
    ) -> None:
        """
        Stop tracking a connected client.

        Only removes the entry when it still belongs to the same client;
        a newer client may already have replaced it for this address.
        """
        if self._tracked_clients.get(address) == on_ble_disconnected:
            del self._tracked_clients[address]

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
        # Heal local client state before notifying subscribers so the
        # published allocation snapshot and the clients' connected state
        # are always consistent with each other.
        self._async_reconcile_connections()
        if (changed or not self._called_callback) and (
            connection_slots_callback := self._connection_slots_callback
        ):
            self._called_callback = True
            connection_slots_callback(
                Allocations(
                    self.mac_address,
                    limit,
                    free,
                    [int_to_bluetooth_address(address) for address in allocated],
                )
            )

    def _async_reconcile_connections(self) -> None:
        """
        Disconnect tracked clients absent from the proxy's allocated list.

        The allocated list is authoritative for which addresses hold a
        connection on the proxy, so a tracked client missing from it lost
        its connection and the ``connected=false`` notification was lost
        (congested link, or an ESP-side link loss that never produced a
        notification). Firing its disconnect handler
        tears down the client state and lets the consumer reconnect
        instead of holding a phantom connection forever.

        Only trusted when the list length matches the used slot count.
        Firmware maintains ``free`` and ``allocated`` as one fact (an
        address enters the list at slot reservation, before the link is
        even attempted), so the lengths always match on firmware that
        reports the list; older firmware reports ``free``/``limit`` with
        no ``allocated`` at all, which looks like an empty list, and the
        mismatch skips reconciliation so nothing is torn down on it.
        """
        allocated = self.ble_allocations
        used = self.ble_connections_limit - self.ble_connections_free
        if len(allocated) != used:
            if self._tracked_clients:
                _LOGGER.debug(
                    "%s [%s]: Skipping connection reconcile, allocated list"
                    " not trusted: used=%s allocated=%s",
                    self.name,
                    self.mac_address,
                    used,
                    allocated,
                )
            return
        # Snapshot: handlers untrack themselves during the loop.
        for address, on_ble_disconnected in list(self._tracked_clients.items()):
            if address in allocated:
                continue
            # Warning: this means the proxy's connected=false notification
            # was lost (congested link, or an ESP-side link loss that
            # never produced one); the state was out of sync until this
            # self heal.
            _LOGGER.warning(
                "%s [%s]: Reconciling stale connection to %s: "
                "not in allocated list %s",
                self.name,
                self.mac_address,
                int_to_bluetooth_address(address),
                allocated,
            )
            # Untrack before invoking so the teardown is attempted exactly
            # once; if the handler raises partway (it ends in consumer
            # supplied code) the entry must not linger and re-fire the
            # warning plus traceback on every later slot update.
            self.async_untrack_client(address, on_ble_disconnected)
            try:
                on_ble_disconnected()
            except Exception:  # pylint: disable=broad-except
                # One raising handler must not strand the remaining stale
                # clients until the next slot change.
                _LOGGER.exception(
                    "%s [%s]: Error reconciling stale connection to %s",
                    self.name,
                    self.mac_address,
                    int_to_bluetooth_address(address),
                )

    def _wait_for_ble_connections_free_timeout(self, fut: asyncio.Future[int]) -> None:
        """Timeout the wait_for_ble_connections_free future."""
        if not fut.done():
            # A bare ``TimeoutError()`` surfaces to the bleak consumer with no
            # context; name the saturated proxy and its current slot state so
            # the failure is actionable instead of an anonymous timeout.
            fut.set_exception(
                TimeoutError(
                    f"{self.name} [{self.mac_address}]: No free BLE connection "
                    f"slot became available (limit={self.ble_connections_limit}, "
                    f"in use={self.ble_connections_limit - self.ble_connections_free})"
                )
            )

    async def wait_for_ble_connections_free(self, timeout: float) -> int:
        """
        Wait until there are free BLE connection slots on this device.

        Returns immediately with the current free count if slots are already
        available. Otherwise waits up to ``timeout`` seconds for the proxy to
        report at least one free slot via ``async_update_ble_connection_limits``.

        Raises:
            TimeoutError: if no slot becomes free within ``timeout`` seconds.

        """
        if self.ble_connections_free > 0:
            return self.ble_connections_free
        fut: asyncio.Future[int] = self.loop.create_future()
        self._ble_connection_free_futures.add(fut)
        cancel_timeout = self.loop.call_later(
            timeout, self._wait_for_ble_connections_free_timeout, fut
        )
        try:
            return await fut
        finally:
            cancel_timeout.cancel()
            self._ble_connection_free_futures.discard(fut)
