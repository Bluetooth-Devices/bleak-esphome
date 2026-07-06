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
    from collections.abc import Callable

    from .device import ESPHomeBluetoothDevice

_LOGGER = logging.getLogger(__name__)

# The firmware answers a successful advertisement subscription with an
# immediate BluetoothScannerStateResponse (both shipped in esphome 2025.5
# with FEATURE_STATE_AND_MODE). If none arrives, the subscription was
# silently rejected because a stale connection from a previous session
# still holds the device's single subscriber slot; the device reaps such
# connections via its keepalive after ~150s, so retry until one lands.
# The last delay repeats.
_SUBSCRIPTION_RETRY_DELAYS = (10.0, 30.0, 60.0)

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
        "_resubscribe_advertisements",
        "_scanner_state_seen",
        "_subscription_watchdog_task",
    )

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the scanner."""
        super().__init__(*args, **kwargs)
        self._bluetooth_device: ESPHomeBluetoothDevice | None = None
        self._client: APIClient | None = None
        self._active_window_lock = asyncio.Lock()
        self._configured_mode: BluetoothScanningMode | None = None
        self._intent: BluetoothScanningMode | None = None
        self._resubscribe_advertisements: Callable[[], object] | None = None
        self._scanner_state_seen = False
        self._subscription_watchdog_task: asyncio.Task[None] | None = None

    @property
    def configured_mode(self) -> BluetoothScanningMode | None:
        """
        The proxy's last-reported configured firmware mode.

        Useful for one-shot migration logic at integration setup (e.g.
        "if the proxy was configured ACTIVE, switch the HA option to
        AUTO"). Caveat: the proto field shipped in esphome 2025.9;
        ``FEATURE_STATE_AND_MODE`` firmware older than that leaves it
        unset, which proto3 decodes as the default ``PASSIVE``,
        indistinguishable from an explicit PASSIVE config.
        """
        return self._configured_mode

    def async_set_scanning_mode(self, mode: BluetoothScanningMode) -> None:
        """
        Pin the scanner to ``mode`` and tell the firmware.

        AUTO maps to PASSIVE on the firmware; the auto-scheduler flips it
        to ACTIVE on demand via :meth:`async_request_active_window`. Once
        called, ``requested_mode`` is no longer overwritten by firmware
        state updates.

        Pinning the local intent always succeeds, but the firmware can
        only be told when the proxy advertises ``FEATURE_STATE_AND_MODE``
        (which is what binds the API client via :meth:`set_client`). On
        older firmware the client is never bound, so the request cannot
        reach the device; a warning is logged and the firmware keeps its
        own configured mode.
        """
        self._intent = mode
        self.set_requested_mode(mode)
        client = self._client
        if client is None:
            _LOGGER.warning(
                "%s: Cannot set scanner mode to %s on the proxy; this ESPHome "
                "version does not support runtime scanner-mode control; "
                "Upgrade the ESPHome version on the device",
                self.name,
                mode.name,
            )
            return
        try:
            client.bluetooth_scanner_set_mode(_HA_TO_FIRMWARE_MODE[mode])
        except APIConnectionError as ex:
            _LOGGER.debug("%s: failed to set scan mode: %s", self.name, ex)

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

    def set_resubscribe_advertisements(self, callback: Callable[[], object]) -> None:
        """
        Bind the callable that re-sends the advertisement subscription.

        Must be called before :meth:`async_setup`; the watchdog is started
        there, only if a callback is already bound, so binding one later
        has no effect. If the proxy never reports scanner state, the
        subscription was silently rejected (the device's single subscriber
        slot was still held by a stale connection) and ``callback`` is
        invoked to try again; its return value (the unsubscribe callable
        from aioesphomeapi) is ignored. Only meaningful for proxies that
        advertise ``FEATURE_STATE_AND_MODE``; older firmware never reports
        scanner state, so the watchdog would resubscribe forever.
        """
        self._resubscribe_advertisements = callback

    def async_setup(self) -> Callable[[], None]:
        """Set up the scanner and start the subscription watchdog if armed."""
        unsetup = super().async_setup()
        if self._resubscribe_advertisements is not None:
            self._subscription_watchdog_task = asyncio.create_task(
                self._subscription_watchdog()
            )

        def _unsetup() -> None:
            if self._subscription_watchdog_task is not None:
                self._subscription_watchdog_task.cancel()
                self._subscription_watchdog_task = None
            unsetup()

        return _unsetup

    async def _subscription_watchdog(self) -> None:
        """Resubscribe advertisements until the proxy reports scanner state."""
        if TYPE_CHECKING:
            assert self._resubscribe_advertisements is not None
        attempt = 0
        while True:
            delay = _SUBSCRIPTION_RETRY_DELAYS[
                min(attempt, len(_SUBSCRIPTION_RETRY_DELAYS) - 1)
            ]
            await asyncio.sleep(delay)
            if self._scanner_state_seen:
                return
            # Warn while a stale subscriber is expected to still hold the slot
            # (the device reaps it within ~150s); past that the fault is
            # persistent and repeating the warning every retry forever would
            # just be log spam, so de-escalate to debug.
            log = (
                _LOGGER.warning
                if attempt < len(_SUBSCRIPTION_RETRY_DELAYS)
                else _LOGGER.debug
            )
            log(
                "%s: No scanner state received %ss after subscribing; the device "
                "likely still has a stale advertisement subscriber from a "
                "previous connection; resubscribing",
                self.name,
                delay,
            )
            try:
                self._resubscribe_advertisements()
            except APIConnectionError as ex:
                # The connection is gone; the reconnect flow builds a new
                # scanner with its own watchdog.
                _LOGGER.debug("%s: failed to resubscribe: %s", self.name, ex)
                return
            except Exception:
                # The task is fire-and-forget, so without this an unexpected
                # error would only surface as "Task exception was never
                # retrieved" at GC time.
                _LOGGER.exception(
                    "%s: unexpected error resubscribing advertisements", self.name
                )
                return
            attempt += 1

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
        self._scanner_state_seen = True
        configured_pb = state.configured_mode
        self._configured_mode = (
            _FIRMWARE_TO_HA_MODE.get(configured_pb)
            if configured_pb is not None
            else None
        )
        mode_pb = state.mode
        mode = _FIRMWARE_TO_HA_MODE.get(mode_pb) if mode_pb is not None else None
        if self._intent is None:
            self.set_requested_mode(mode)
        if state.state == BluetoothScannerState.RUNNING:
            self.set_current_mode(mode)
        else:
            self.set_current_mode(None)

    async def async_request_active_window(self, duration: float) -> bool:
        """
        Flip the proxy to ACTIVE for ``duration`` seconds, then restore.

        Called by habluetooth's auto-mode scheduler. The restore mode
        prefers the integration's pinned intent (set via
        :meth:`async_set_scanning_mode`) — so AUTO returns to PASSIVE on
        the firmware even though ``requested_mode`` stays AUTO — and
        falls back to the last firmware-reported ``requested_mode`` when
        no intent has been pinned. If no prior mode is known the proxy
        is returned to PASSIVE. Only one window may be open at a time;
        a request that arrives while another window is in flight
        returns ``False`` immediately so the caller can decide whether
        to retry.
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
                # Honor a live repin (async_set_scanning_mode is sync and
                # lock-free, so it can land mid-window) over the snapshot
                # taken when the window opened. Fall back to the open-time
                # snapshot only when no intent was ever pinned — there
                # requested_mode tracks firmware and reports ACTIVE
                # mid-window, so a live read would pin ACTIVE forever.
                target = self._intent if self._intent is not None else prior
                restore = (
                    _HA_TO_FIRMWARE_MODE.get(target, BluetoothScannerMode.PASSIVE)
                    if target is not None
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
