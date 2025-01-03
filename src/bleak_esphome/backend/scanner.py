"""Bluetooth scanner for esphome."""

from __future__ import annotations

from typing import Any

from aioesphomeapi import (
    BluetoothLEAdvertisement,
    BluetoothLERawAdvertisementsResponse,
    BluetoothProxyFeature,
)
from bluetooth_data_tools import (
    int_to_bluetooth_address,
    parse_advertisement_data_tuple,
)
from bluetooth_data_tools import (
    monotonic_time_coarse as MONOTONIC_TIME,
)
from habluetooth import BaseHaRemoteScanner, HaBluetoothConnector


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    __slots__ = ("_feature_flags",)

    def __init__(
        self,
        scanner_id: str,
        name: str,
        connector: HaBluetoothConnector | None,
        connectable: bool,
        feature_flags: BluetoothProxyFeature,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(scanner_id, name, connector, connectable)
        self._feature_flags = feature_flags

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostics information."""
        return await super().async_diagnostics() | {
            "feature_flags": self._feature_flags,
        }

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
        for adv in raw.advertisements:
            self._async_on_advertisement(
                int_to_bluetooth_address(adv.address),
                adv.rssi,
                *parse_advertisement_data_tuple((adv.data,)),
                {"address_type": adv.address_type},
                now,
            )
