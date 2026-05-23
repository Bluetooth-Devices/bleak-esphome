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

    __slots__ = (
        "_active_window_lock",
        "_bluetooth_device",
        "_client",
        "_configured_mode",
        "_intent",
        "_original_configured_mode",
    )

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the scanner."""
        super().__init__(*args, **kwargs)
        self._bluetooth_device: ESPHomeBluetoothDevice | None = None
        self._client: APIClient | None = None
        self._active_window_lock = asyncio.Lock()
        self._configured_mode: BluetoothScanningMode | None = None
        self._original_configured_mode: BluetoothScanningMode | None = None
        self._intent: BluetoothScanningMode | None = None

    @property
    def configured_mode(self) -> BluetoothScanningMode | None:
        """
        Return the proxy's configured scanning mode, as last reported.

        Populated from ``BluetoothScannerStateResponse.configured_mode``
        (aioesphomeapi 45.2.0+). The configured mode is the mode the proxy
        was set to via ``bluetooth_scanner_set_mode``, distinct from
        ``current_mode`` which can briefly differ during an on-demand
        active window. Useful for migrating a previously-configured proxy
        to a different default the first time it is observed.
        """
        return self._configured_mode

    async def async_set_scanning_mode(self, mode: BluetoothScanningMode) -> None:
        """
        Set the scanning mode this scanner should run in.

        ``AUTO`` keeps the proxy in PASSIVE on the firmware and relies on
        habluetooth's auto-mode scheduler to flip it to ACTIVE on demand
        via :meth:`async_request_active_window`. ``ACTIVE`` and ``PASSIVE``
        configure the proxy directly. Once called, ``requested_mode`` is
        pinned to the integration's intent and is no longer overwritten by
        firmware state updates.
        """
        self._intent = mode
        self.set_requested_mode(mode)
        client = self._client
        if client is None:
            return
        firmware_mode = (
            BluetoothScannerMode.ACTIVE
            if mode is BluetoothScanningMode.ACTIVE
            else BluetoothScannerMode.PASSIVE
        )
        try:
            client.bluetooth_scanner_set_mode(firmware_mode)
        except APIConnectionError as ex:
            _LOGGER.debug("%s: failed to set scan mode: %s", self.name, ex)

    async def async_restore_configured_mode(self) -> None:
        """
        Restore the proxy to the mode it was first observed configured for.

        Called by the integration on Home Assistant shutdown so the proxy
        does not stay pinned to whatever mode the integration last set
        (for example PASSIVE while AUTO was in use). The snapshot is
        taken from the first ``configured_mode`` reported by the firmware
        and is never updated after that, so it reflects the proxy's
        natural configuration. If no configured_mode has been observed
        or no API client is bound, this is a no-op.
        """
        client = self._client
        original = self._original_configured_mode
        if client is None or original is None:
            return
        firmware_mode = (
            BluetoothScannerMode.ACTIVE
            if original is BluetoothScanningMode.ACTIVE
            else BluetoothScannerMode.PASSIVE
        )
        try:
            client.bluetooth_scanner_set_mode(firmware_mode)
        except APIConnectionError as ex:
            _LOGGER.debug("%s: failed to restore configured mode: %s", self.name, ex)

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

        ``state.mode`` is the proxy's current scanning mode, which can flip
        between ACTIVE and PASSIVE during an on-demand active window even
        when ``configured_mode`` stays the same. ``current_mode`` is only
        set when ``state.state`` is ``RUNNING`` — IDLE, STARTING, STOPPING,
        STOPPED, and FAILED all mean the proxy is not actively scanning.

        ``requested_mode`` reflects the integration's intent once
        :meth:`async_set_scanning_mode` has been called. Before that, it
        falls back to ``state.mode`` so callers that never set an explicit
        intent keep the historical behavior.
        """
        configured_pb = state.configured_mode
        if configured_pb == BluetoothScannerMode.ACTIVE:
            self._configured_mode = BluetoothScanningMode.ACTIVE
        elif configured_pb == BluetoothScannerMode.PASSIVE:
            self._configured_mode = BluetoothScanningMode.PASSIVE
        else:
            self._configured_mode = None
        if self._original_configured_mode is None and self._configured_mode is not None:
            self._original_configured_mode = self._configured_mode
        if state.mode == BluetoothScannerMode.ACTIVE:
            mode: BluetoothScanningMode | None = BluetoothScanningMode.ACTIVE
        elif state.mode == BluetoothScannerMode.PASSIVE:
            mode = BluetoothScanningMode.PASSIVE
        else:
            mode = None
        if self._intent is None:
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
            prior = self._intent if self._intent is not None else self.requested_mode
            try:
                client.bluetooth_scanner_set_mode(BluetoothScannerMode.ACTIVE)
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
                # bluetooth_scanner_set_mode is a sync method that just
                # queues the request on the API connection and returns
                # None, so the only failure mode here is an immediate
                # APIConnectionError if the connection has gone away.
                # No shield is needed because nothing here yields.
                try:
                    client.bluetooth_scanner_set_mode(restore)
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
