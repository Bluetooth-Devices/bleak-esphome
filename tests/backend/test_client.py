from unittest.mock import patch
from uuid import UUID

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
from bleak.exc import BleakError
from habluetooth import BaseHaRemoteScanner, HaBluetoothConnector

from bleak_esphome.backend.cache import ESPHomeBluetoothCache
from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner

from .. import generate_ble_device

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


def split_uuid(uuid: str) -> list[int]:
    int_128 = UUID(uuid).int
    return [int_128 >> 64, int_128 & 0xFFFFFFFFFFFFFFFF]


@pytest.fixture
def esphome_bluetooth_gatt_services() -> ESPHomeBluetoothGATTServices:
    return ESPHomeBluetoothGATTServices(
        address=57911560448430,
        services=[
            BluetoothGATTService(
                uuid=split_uuid("00001800-0000-1000-8000-00805f9b34fb"),
                handle=1,
                characteristics=[
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a00-0000-1000-8000-00805f9b34fb"),
                        handle=3,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a01-0000-1000-8000-00805f9b34fb"),
                        handle=5,
                        properties=2,
                        descriptors=[],
                    ),
                ],
            ),
            BluetoothGATTService(
                uuid=split_uuid("00001801-0000-1000-8000-00805f9b34fb"),
                handle=6,
                characteristics=[
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a05-0000-1000-8000-00805f9b34fb"),
                        handle=8,
                        properties=32,
                        descriptors=[
                            BluetoothGATTDescriptor(
                                uuid=split_uuid("00002902-0000-1000-8000-00805f9b34fb"),
                                handle=9,
                            )
                        ],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002b3a-0000-1000-8000-00805f9b34fb"),
                        handle=11,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002b29-0000-1000-8000-00805f9b34fb"),
                        handle=13,
                        properties=10,
                        descriptors=[],
                    ),
                ],
            ),
            BluetoothGATTService(
                uuid=split_uuid("d30a7847-e12b-09a8-b04b-8e0922a9abab"),
                handle=14,
                characteristics=[
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("030b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=16,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("040b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=18,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("090b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=20,
                        properties=10,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("050b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=22,
                        properties=10,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("060b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=24,
                        properties=8,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("070b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=26,
                        properties=8,
                        descriptors=[],
                    ),
                ],
            ),
            BluetoothGATTService(
                uuid=split_uuid("0000180a-0000-1000-8000-00805f9b34fb"),
                handle=27,
                characteristics=[
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a29-0000-1000-8000-00805f9b34fb"),
                        handle=29,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a24-0000-1000-8000-00805f9b34fb"),
                        handle=31,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a25-0000-1000-8000-00805f9b34fb"),
                        handle=33,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a26-0000-1000-8000-00805f9b34fb"),
                        handle=35,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a27-0000-1000-8000-00805f9b34fb"),
                        handle=37,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("00002a28-0000-1000-8000-00805f9b34fb"),
                        handle=39,
                        properties=2,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("0a0b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=41,
                        properties=10,
                        descriptors=[],
                    ),
                    BluetoothGATTCharacteristic(
                        uuid=split_uuid("0b0b7847-e12b-09a8-b04b-8e0922a9abab"),
                        handle=43,
                        properties=10,
                        descriptors=[],
                    ),
                ],
            ),
        ],
    )


def test_get_services() -> None:
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)
    assert isinstance(scanner, BaseHaRemoteScanner)


@pytest.fixture(name="client_data")
async def client_data_fixture(mock_client: APIClient) -> ESPHomeClientData:
    """Return a client data fixture."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    return ESPHomeClientData(
        bluetooth_device=ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS),
        cache=ESPHomeBluetoothCache(),
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


async def test_client_usage_while_not_connected(client_data: ESPHomeClientData) -> None:
    """Test client usage while not connected."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    client = ESPHomeClient(ble_device, client_data=client_data)
    with pytest.raises(
        BleakError, match=f"{ESP_NAME}.*{ESP_MAC_ADDRESS}.*not connected"
    ):
        await client.write_gatt_char("test", b"test")


async def test_client_get_services(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test getting client services."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    client = ESPHomeClient(ble_device, client_data=client_data)
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await client.get_services()

    assert services == esphome_bluetooth_gatt_services
