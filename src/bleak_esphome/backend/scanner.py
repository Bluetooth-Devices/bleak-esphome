"""Bluetooth scanner for esphome."""

from __future__ import annotations

from aioesphomeapi import BluetoothLEAdvertisement, BluetoothLERawAdvertisementsResponse
from bluetooth_data_tools import (
    int_to_bluetooth_address,
)
from bluetooth_data_tools import (
    monotonic_time_coarse as MONOTONIC_TIME,
)
from habluetooth import BaseHaRemoteScanner


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    __slots__ = ()

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
        advertisements = raw.advertisements
        # We avoid __iter__ on the protobuf object because
        # the the protobuf library has an expensive internal
        # debug logging when it reaches the end of a repeated field.
        # https://github.com/Bluetooth-Devices/bleak-esphome/pull/90
        # To work around this we use a for loop to iterate over
        # the repeated field since `PyUpb_RepeatedContainer_Subscript`
        # does not trigger the debug logging.
        self._async_on_raw_advertisement(
            [
                (adv.address, adv.rssi, (adv.data,), {"address_type": adv.address_type})
                for i in range(len(advertisements))
                if (adv := advertisements[i]) is not None
            ]
        )
