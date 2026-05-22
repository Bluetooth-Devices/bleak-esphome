"""Bluetooth scanner for esphome."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import TYPE_CHECKING, Any

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    BluetoothLEAdvertisement,
    BluetoothLERawAdvertisementsResponse,
    BluetoothScannerMode,
    BluetoothScannerState,
    BluetoothScannerStateResponse,
)
from bluetooth_data_tools import (
    int_to_bluetooth_address,
)
from bluetooth_data_tools import (
    monotonic_time_coarse as MONOTONIC_TIME,
)
from habluetooth import Allocations, BluetoothScanningMode
from habluetooth.base_scanner import BaseHaRemoteScanner

if TYPE_CHECKING:
    from .device import ESPHomeBluetoothDevice

_LOGGER = logging.getLogger(__name__)


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    __slots__ = ("_active_window_lock", "_bluetooth_device", "_client")

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the scanner."""
        super().__init__(*args, **kwargs)
        self._bluetooth_device: ESPHomeBluetoothDevice | None = None
        self._client: APIClient | None = None
        self._active_window_lock = asyncio.Lock()

    def set_bluetooth_device(self, device: ESPHomeBluetoothDevice) -> None:
        """Set the bluetooth device for this scanner."""
        self._bluetooth_device = device

    def set_client(self, client: APIClient) -> None:
        """
        Bind the API client used to send scanner-mode requests.

        Required for ``async_request_active_window`` to actually flip the
        proxy; without it, requests are silently ignored. Only meaningful
        for proxies that advertise the ``FEATURE_STATE_AND_MODE`` flag.
        """
        self._client = client

    def get_allocations(self) -> Allocations | None:
        """
        Get current connection slot allocations for this ESPHome device.

        Returns:
            Allocations object with free/limit/allocated info, or None if not available.

        """
        if not self._bluetooth_device:
            return None

        # Only return allocations if we have slot info
        if self._bluetooth_device.ble_connections_limit > 0:
            return Allocations(
                adapter=self.source,
                slots=self._bluetooth_device.ble_connections_limit,
                free=self._bluetooth_device.ble_connections_free,
                allocated=[
                    int_to_bluetooth_address(address)
                    for address in self._bluetooth_device.ble_allocations
                ],
            )
        return None

    def async_update_scanner_state(self, state: BluetoothScannerStateResponse) -> None:
        """
        Update the scanner state.

        ``state.mode`` reflects the scanner's configured mode (active vs passive)
        and is reported as the requested mode. ``current_mode`` is only set when
        ``state.state`` is ``RUNNING`` — IDLE, STARTING, STOPPING, STOPPED, and
        FAILED all mean the proxy is not actively scanning, regardless of the
        mode it was configured with.
        """
        if state.mode == BluetoothScannerMode.ACTIVE:
            mode: BluetoothScanningMode | None = BluetoothScanningMode.ACTIVE
        elif state.mode == BluetoothScannerMode.PASSIVE:
            mode = BluetoothScanningMode.PASSIVE
        else:
            mode = None
        self.set_requested_mode(mode)
        if state.state == BluetoothScannerState.RUNNING:
            self.set_current_mode(mode)
        else:
            self.set_current_mode(None)

    async def async_request_active_window(self, duration: float) -> bool:
        """
        Flip the proxy to ACTIVE for ``duration`` seconds, then restore.

        Called by habluetooth's auto-mode scheduler. Restores the proxy
        to whatever mode it last reported via ``async_update_scanner_state``;
        if the prior mode is unknown the proxy is returned to PASSIVE.
        Only one window may be open at a time; a request that arrives
        while another window is in flight returns ``False`` immediately
        so the caller can decide whether to retry.
        """
        client = self._client
        if client is None:
            return False
        # Defensive: guard the asyncio.sleep against non-finite / negative
        # durations that an external caller might pass. Negative or NaN
        # would otherwise propagate into a confusing scheduler error.
        if not math.isfinite(duration) or duration < 0:
            return False
        # Safe: no await between the .locked() check and the acquire
        # inside `async with`, so asyncio cannot schedule another
        # coroutine in between and the check / acquire is effectively
        # atomic on this lock.
        if self._active_window_lock.locked():
            return False
        async with self._active_window_lock:
            prior = self.requested_mode
            try:
                await client.bluetooth_scanner_set_mode(BluetoothScannerMode.ACTIVE)
            except APIConnectionError as ex:
                _LOGGER.debug(
                    "%s: failed to enter active scan window: %s", self.name, ex
                )
                return False
            try:
                await asyncio.sleep(duration)
            finally:
                restore = (
                    BluetoothScannerMode.ACTIVE
                    if prior is BluetoothScanningMode.ACTIVE
                    else BluetoothScannerMode.PASSIVE
                )
                # Shield the restore from ordinary task cancellation so
                # the proxy is not abandoned in ACTIVE; the cancellation
                # still propagates to the caller once the restore
                # completes. This does NOT cover full interpreter / event
                # loop shutdown: once the loop is closing, the detached
                # restore task will not get scheduled and the proxy may
                # be left in ACTIVE until the connection drops.
                try:
                    await asyncio.shield(client.bluetooth_scanner_set_mode(restore))
                except APIConnectionError as ex:
                    _LOGGER.warning(
                        "%s: failed to restore scan mode after active window: %s",
                        self.name,
                        ex,
                    )
        return True

    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        # The mac address is a uint64, but we need a string
        self._async_on_advertisement(
            int_to_bluetooth_address(adv.address),
            adv.rssi,
            adv.name,
            adv.service_uuids,
            adv.service_data,
            adv.manufacturer_data,
            None,
            {"address_type": adv.address_type},
            MONOTONIC_TIME(),
        )

    def async_on_raw_advertisements(
        self, raw: BluetoothLERawAdvertisementsResponse
    ) -> None:
        """Call the registered callback."""
        now = MONOTONIC_TIME()
        advertisements = raw.advertisements
        # We avoid __iter__ on the protobuf object because
        # the the protobuf library has an expensive internal
        # debug logging when it reaches the end of a repeated field.
        # https://github.com/Bluetooth-Devices/bleak-esphome/pull/90
        # To work around this we use a for loop to iterate over
        # the repeated field since `PyUpb_RepeatedContainer_Subscript`
        # does not trigger the debug logging.
        on_raw = self._async_on_raw_advertisement
        for i in range(len(advertisements)):
            adv = advertisements[i]
            on_raw(
                int_to_bluetooth_address(adv.address),
                adv.rssi,
                adv.data,
                {"address_type": adv.address_type},
                now,
            )
