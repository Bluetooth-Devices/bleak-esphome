"""Bluetooth scanner for esphome."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aioesphomeapi import (
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


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    __slots__ = ("_address_type_details", "_bluetooth_device")

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the scanner."""
        super().__init__(*args, **kwargs)
        self._bluetooth_device: ESPHomeBluetoothDevice | None = None
        # Per-address-type ``{"address_type": int}`` dict cache. The base
        # scanner copies ``details`` via ``{**self._details, **details}`` on
        # the first advertisement for an address and never mutates it again
        # (subsequent advertisements reuse the previously-built ``BLEDevice``
        # and ignore ``details`` entirely), so the cached dict can be shared
        # safely across iterations. BLE address types are a small bounded
        # set (PUBLIC=0, RANDOM=1, plus the two identity variants), so the
        # cache stays tiny.
        self._address_type_details: dict[int, dict[str, int]] = {}

    def set_bluetooth_device(self, device: ESPHomeBluetoothDevice) -> None:
        """Set the bluetooth device for this scanner."""
        self._bluetooth_device = device

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

    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        # The mac address is a uint64, but we need a string
        address_type = adv.address_type
        details_cache = self._address_type_details
        if (details := details_cache.get(address_type)) is None:
            details = {"address_type": address_type}
            details_cache[address_type] = details
        self._async_on_advertisement(
            int_to_bluetooth_address(adv.address),
            adv.rssi,
            adv.name,
            adv.service_uuids,
            adv.service_data,
            adv.manufacturer_data,
            None,
            details,
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
        details_cache = self._address_type_details
        for i in range(len(advertisements)):
            adv = advertisements[i]
            address_type = adv.address_type
            if (details := details_cache.get(address_type)) is None:
                details = {"address_type": address_type}
                details_cache[address_type] = details
            on_raw(
                int_to_bluetooth_address(adv.address),
                adv.rssi,
                adv.data,
                details,
                now,
            )
