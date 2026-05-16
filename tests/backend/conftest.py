"""Shared fixtures and helpers for ``tests/backend``."""

from __future__ import annotations

from typing import Any

import pytest
from aioesphomeapi import (
    APIClient,
    APIVersion,
    BluetoothGATTCharacteristic,
    BluetoothGATTDescriptor,
    BluetoothGATTService,
    BluetoothProxyFeature,
    DeviceInfo,
    ESPHomeBluetoothGATTServices,
)
from bleak.backends.device import BLEDevice
from habluetooth import HaBluetoothConnector
from pytest_asyncio import fixture as aio_fixture

from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner

from .. import generate_ble_device

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


def _make_client_backend(
    client_data: ESPHomeClientData,
) -> type[ESPHomeClient]:
    """Create a backend class with client_data bound."""

    class _ESPHomeClientBackend(ESPHomeClient):
        """ESPHome client backend with bound client_data."""

        __name__ = "ESPHomeClient"

        def __init__(
            self, address_or_ble_device: BLEDevice | str, *args: Any, **kwargs: Any
        ) -> None:
            """Initialize the ESPHomeClient with bound client_data."""
            super().__init__(
                address_or_ble_device, *args, client_data=client_data, **kwargs
            )

    return _ESPHomeClientBackend


def _make_client(client_data: ESPHomeClientData) -> ESPHomeClient:
    """Build an ``ESPHomeClient`` bound to ``client_data``."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF",
        details={"source": ESP_MAC_ADDRESS, "address_type": 1},
    )
    return ESPHomeClient(ble_device, client_data=client_data)


@aio_fixture(name="client_data")
async def client_data_fixture(mock_client: APIClient) -> ESPHomeClientData:
    """Return a client data fixture."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    return ESPHomeClientData(
        bluetooth_device=ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS),
        client=mock_client,
        device_info=DeviceInfo(
            mac_address=ESP_MAC_ADDRESS,
            name=ESP_NAME,
            bluetooth_proxy_feature_flags=BluetoothProxyFeature.PASSIVE_SCAN
            | BluetoothProxyFeature.ACTIVE_CONNECTIONS
            | BluetoothProxyFeature.REMOTE_CACHING
            | BluetoothProxyFeature.PAIRING
            | BluetoothProxyFeature.CACHE_CLEARING
            | BluetoothProxyFeature.RAW_ADVERTISEMENTS,
        ),
        api_version=APIVersion(1, 9),
        title=ESP_NAME,
        scanner=ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True),
    )


@pytest.fixture
def esphome_bluetooth_gatt_services() -> ESPHomeBluetoothGATTServices:
    """Return a populated ``ESPHomeBluetoothGATTServices`` payload."""
    service1 = BluetoothGATTService(
        uuid="00001800-0000-1000-8000-00805f9b34fb",
        handle=1,
        characteristics=[],
    )
    object.__setattr__(
        service1,
        "characteristics",
        [
            BluetoothGATTCharacteristic(
                uuid="00002a00-0000-1000-8000-00805f9b34fb",
                handle=3,
                properties=2,
                descriptors=[],
            ),
            BluetoothGATTCharacteristic(
                uuid="00002a01-0000-1000-8000-00805f9b34fb",
                handle=5,
                properties=2,
                descriptors=[],
            ),
        ],
    )
    service2 = BluetoothGATTService(
        uuid="00001801-0000-1000-8000-00805f9b34fb",
        handle=6,
        characteristics=[],
    )
    service2_chars = [
        BluetoothGATTCharacteristic(
            uuid="00002a05-0000-1000-8000-00805f9b34fb",
            handle=8,
            properties=32,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002b3a-0000-1000-8000-00805f9b34fb",
            handle=11,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002b29-0000-1000-8000-00805f9b34fb",
            handle=13,
            properties=10,
            descriptors=[],
        ),
    ]
    object.__setattr__(
        service2_chars[0],
        "descriptors",
        [
            BluetoothGATTDescriptor(
                uuid="00002902-0000-1000-8000-00805f9b34fb",
                handle=9,
            )
        ],
    )
    object.__setattr__(service2, "characteristics", service2_chars)

    service3 = BluetoothGATTService(
        uuid="d30a7847-e12b-09a8-b04b-8e0922a9abab",
        handle=14,
        characteristics=[],
    )
    service3_chars = [
        BluetoothGATTCharacteristic(
            uuid="030b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=16,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="040b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=18,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="090b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=20,
            properties=10,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="050b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=22,
            properties=10,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="060b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=24,
            properties=8,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="070b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=26,
            properties=8,
            descriptors=[],
        ),
    ]
    object.__setattr__(service3, "characteristics", service3_chars)
    service4 = BluetoothGATTService(
        uuid="0000180a-0000-1000-8000-00805f9b34fb",
        handle=27,
        characteristics=[],
    )
    service4_chars = [
        BluetoothGATTCharacteristic(
            uuid="00002a29-0000-1000-8000-00805f9b34fb",
            handle=29,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002a24-0000-1000-8000-00805f9b34fb",
            handle=31,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002a25-0000-1000-8000-00805f9b34fb",
            handle=33,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002a26-0000-1000-8000-00805f9b34fb",
            handle=35,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002a27-0000-1000-8000-00805f9b34fb",
            handle=37,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="00002a28-0000-1000-8000-00805f9b34fb",
            handle=39,
            properties=2,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="0a0b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=41,
            properties=10,
            descriptors=[],
        ),
        BluetoothGATTCharacteristic(
            uuid="0b0b7847-e12b-09a8-b04b-8e0922a9abab",
            handle=43,
            properties=10,
            descriptors=[],
        ),
    ]
    object.__setattr__(service4, "characteristics", service4_chars)
    return ESPHomeBluetoothGATTServices(
        address=57911560448430,
        services=[service1, service2, service3, service4],
    )
