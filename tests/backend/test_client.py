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
from pytest_asyncio import fixture as aio_fixture

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

    service1 = BluetoothGATTService(
        uuid=split_uuid("00001800-0000-1000-8000-00805f9b34fb"),
        handle=1,
        characteristics=[],
    )
    object.__setattr__(
        service1,
        "characteristics",
        [
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
    )
    service2 = BluetoothGATTService(
        uuid=split_uuid("00001801-0000-1000-8000-00805f9b34fb"),
        handle=6,
        characteristics=[],
    )
    service2_chars = [
        BluetoothGATTCharacteristic(
            uuid=split_uuid("00002a05-0000-1000-8000-00805f9b34fb"),
            handle=8,
            properties=32,
            descriptors=[],
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
    ]
    object.__setattr__(
        service2_chars[0],
        "descriptors",
        [
            BluetoothGATTDescriptor(
                uuid=split_uuid("00002902-0000-1000-8000-00805f9b34fb"),
                handle=9,
            )
        ],
    )
    object.__setattr__(service2, "characteristics", service2_chars)

    service3 = BluetoothGATTService(
        uuid=split_uuid("d30a7847-e12b-09a8-b04b-8e0922a9abab"),
        handle=14,
        characteristics=[],
    )
    service3_chars = [
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
    ]
    object.__setattr__(service3, "characteristics", service3_chars)
    service4 = BluetoothGATTService(
        uuid=split_uuid("0000180a-0000-1000-8000-00805f9b34fb"),
        handle=27,
        characteristics=[],
    )
    service4_chars = [
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
    ]
    object.__setattr__(service4, "characteristics", service4_chars)
    return ESPHomeBluetoothGATTServices(
        address=57911560448430,
        services=[service1, service2, service3, service4],
    )


def test_get_services() -> None:
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)
    assert isinstance(scanner, BaseHaRemoteScanner)


@aio_fixture(name="client_data")
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_client_get_services_and_write(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test getting client services and writing a GATT char."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    client = ESPHomeClient(ble_device, client_data=client_data)
    client._is_connected = True
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await client.get_services()

    assert services is not None

    char = client._resolve_characteristic(
        char_specifier="090b7847-e12b-09a8-b04b-8e0922a9abab",
    )
    assert char is not None
    assert char.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char.properties == ["read", "write"]
    assert char.handle == 20

    char2 = services.get_characteristic("090b7847-e12b-09a8-b04b-8e0922a9abab")
    assert char2 is not None
    assert char2.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char2.properties == ["read", "write"]
    assert char2.handle == 20

    char3 = services.get_characteristic(UUID("090b7847-e12b-09a8-b04b-8e0922a9abab"))
    assert char3 is not None
    assert char3.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char3.properties == ["read", "write"]
    assert char3.handle == 20

    with patch.object(
        client._client,
        "bluetooth_gatt_write",
    ) as mock_write:
        await client.write_gatt_char(
            "090b7847-e12b-09a8-b04b-8e0922a9abab",
            b"test",
            True,
        )

    mock_write.assert_called_once_with(225106397622015, 20, b"test", True)