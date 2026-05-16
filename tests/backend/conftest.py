"""Shared fixtures for ``tests/backend``."""

from __future__ import annotations

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
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from habluetooth import HaBluetoothConnector
from pytest_asyncio import fixture as aio_fixture

from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner

from ._helpers import ESP_MAC_ADDRESS, ESP_NAME, make_ble_device, make_bleak_client


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


@pytest.fixture
def ble_device() -> BLEDevice:
    """Return the standard remote BLE device used by tests."""
    return make_ble_device()


@aio_fixture(name="esphome_client")
async def esphome_client_fixture(
    client_data: ESPHomeClientData, ble_device: BLEDevice
) -> ESPHomeClient:
    """Return a fresh ``ESPHomeClient`` bound to ``client_data``."""
    return ESPHomeClient(ble_device, client_data=client_data)


@aio_fixture(name="connected_client")
async def connected_client_fixture(
    esphome_client: ESPHomeClient,
) -> ESPHomeClient:
    """Return an ``ESPHomeClient`` already marked as connected."""
    esphome_client._is_connected = True
    return esphome_client


@aio_fixture(name="bleak_pair")
async def bleak_pair_fixture(
    client_data: ESPHomeClientData,
) -> tuple[BleakClient, ESPHomeClient]:
    """Return ``(BleakClient, ESPHomeClient backend)`` with 10 free slots."""
    return make_bleak_client(client_data)


@aio_fixture(name="bluetooth_device")
async def bluetooth_device_fixture() -> ESPHomeBluetoothDevice:
    """Return a fresh ``ESPHomeBluetoothDevice`` for the standard proxy."""
    return ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
