"""Bluetooth scanner for esphome."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aioesphomeapi import (
    BluetoothLEAdvertisement,
    BluetoothLERawAdvertisementsResponse,
    BluetoothScannerMode,
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

    __slots__ = ("_bluetooth_device",)

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the scanner."""
        super().__init__(*args, **kwargs)
        self._bluetooth_device: ESPHomeBluetoothDevice | None = None

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
                allocated=list(self._bluetooth_device.ble_allocations),
            )
        return None

    def async_update_scanner_state(self, state: BluetoothScannerStateResponse) -> None:
        """Update the scanner state."""
        if state.mode == BluetoothScannerMode.ACTIVE:
            self.set_requested_mode(BluetoothScanningMode.ACTIVE)
            self.set_current_mode(BluetoothScanningMode.ACTIVE)
        elif state.mode == BluetoothScannerMode.PASSIVE:
            self.set_requested_mode(BluetoothScanningMode.PASSIVE)
            self.set_current_mode(BluetoothScanningMode.PASSIVE)
        else:
            self.set_current_mode(None)
            self.set_requested_mode(None)

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
