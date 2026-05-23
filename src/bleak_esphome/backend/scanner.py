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

# Firmware (BluetoothScannerMode) -> habluetooth (BluetoothScanningMode).
_FIRMWARE_TO_HA_MODE: dict[BluetoothScannerMode, BluetoothScanningMode] = {
    BluetoothScannerMode.ACTIVE: BluetoothScanningMode.ACTIVE,
    BluetoothScannerMode.PASSIVE: BluetoothScanningMode.PASSIVE,
}

# Integration intent (BluetoothScanningMode) -> firmware (BluetoothScannerMode).
# AUTO is a habluetooth-only mode; on the proxy it maps to PASSIVE and the
# auto-mode scheduler flips to ACTIVE on demand via async_request_active_window.
_HA_TO_FIRMWARE_MODE: dict[BluetoothScanningMode, BluetoothScannerMode] = {
    BluetoothScanningMode.ACTIVE: BluetoothScannerMode.ACTIVE,
    BluetoothScanningMode.PASSIVE: BluetoothScannerMode.PASSIVE,
    BluetoothScanningMode.AUTO: BluetoothScannerMode.PASSIVE,
}


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
        """The proxy's last-reported configured firmware mode."""
        return self._configured_mode

    def async_set_scanning_mode(self, mode: BluetoothScanningMode) -> None:
        """
        Pin the scanner to ``mode`` and tell the firmware.

        AUTO maps to PASSIVE on the firmware; the auto-scheduler flips it
        to ACTIVE on demand via :meth:`async_request_active_window`. Once
        called, ``requested_mode`` is no longer overwritten by firmware
        state updates.
        """
        self._intent = mode
        self.set_requested_mode(mode)
        client = self._client
        if client is None:
            return
        firmware_mode = _HA_TO_FIRMWARE_MODE[mode]
        if self._configured_mode is _FIRMWARE_TO_HA_MODE[firmware_mode]:
            return
        try:
            client.bluetooth_scanner_set_mode(firmware_mode)
        except APIConnectionError as ex:
            _LOGGER.debug("%s: failed to set scan mode: %s", self.name, ex)

    def async_restore_configured_mode(self) -> None:
        """
        Replay the first-observed ``configured_mode`` to the proxy.

        Intended for HA shutdown so the proxy doesn't stay pinned to the
        mode HA last set (e.g. PASSIVE while AUTO was in use). No-op if no
        configured_mode has been observed or no API client is bound.
        """
        client = self._client
        original = self._original_configured_mode
        if client is None or original is None or original is self._configured_mode:
            return
        try:
            client.bluetooth_scanner_set_mode(_HA_TO_FIRMWARE_MODE[original])
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
        Apply a firmware scanner-state update.

        ``state.mode`` is the current mode (may flip during an active
        window); ``state.configured_mode`` is the configured firmware
        mode. ``current_mode`` is cleared when ``state.state`` is not
        RUNNING. ``requested_mode`` follows the integration's intent once
        :meth:`async_set_scanning_mode` has been called, otherwise it
        falls back to ``state.mode``.
        """
        configured = _FIRMWARE_TO_HA_MODE.get(state.configured_mode)
        self._configured_mode = configured
        if self._original_configured_mode is None and configured is not None:
            self._original_configured_mode = configured
        mode = _FIRMWARE_TO_HA_MODE.get(state.mode)
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
                restore = _HA_TO_FIRMWARE_MODE.get(prior, BluetoothScannerMode.PASSIVE)
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
