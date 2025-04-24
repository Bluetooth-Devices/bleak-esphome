"""Bluetooth scanner for esphome."""

from __future__ import annotations

from aioesphomeapi import (
    BluetoothLEAdvertisement,
    BluetoothLERawAdvertisement,
    BluetoothLERawAdvertisementsResponse,
)
from bluetooth_data_tools import (
    int_to_bluetooth_address,
    parse_advertisement_data_tuple,
)
from bluetooth_data_tools import (
    monotonic_time_coarse as MONOTONIC_TIME,
)
from habluetooth.base_scanner import BaseHaRemoteScanner

BLEResponse_advertisements = BluetoothLERawAdvertisementsResponse.advertisements
BLE_address = BluetoothLERawAdvertisement.address
BLE_data = BluetoothLERawAdvertisement.data
BLE_rssi = BluetoothLERawAdvertisement.rssi
BLE_address_type = BluetoothLERawAdvertisement.address_type


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
        now = MONOTONIC_TIME()
        advertisements = BLEResponse_advertisements(raw)
        # We avoid __iter__ on the protobuf object because
        # the the protobuf library has an expensive internal
        # debug logging when it reaches the end of a repeated field.
        # https://github.com/Bluetooth-Devices/bleak-esphome/pull/90
        # To work around this we use a for loop to iterate over
        # the repeated field since `PyUpb_RepeatedContainer_Subscript`
        # does not trigger the debug logging.
        for i in range(len(advertisements)):
            adv = advertisements[i]
            parsed: tuple = parse_advertisement_data_tuple((BLE_data(adv),))  # type: ignore[type-arg]
            self._async_on_advertisement(
                int_to_bluetooth_address(BLE_address(adv)),
                BLE_rssi(adv),
                parsed[0],
                parsed[1],
                parsed[2],
                parsed[3],
                parsed[4],
                {"address_type": BLE_address_type(adv)},
                now,
            )
