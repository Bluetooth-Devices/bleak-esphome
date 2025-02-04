import asyncio
from functools import partial
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
from bleak import BleakClient
from bleak.exc import BleakError
from habluetooth import BaseHaRemoteScanner, HaBluetoothConnector
from pytest_asyncio import fixture as aio_fixture

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
async def test_client_get_services_and_read_write(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test getting client services and read/write a GATT char."""
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

    with patch.object(
        client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await client.read_gatt_char(
            "090b7847-e12b-09a8-b04b-8e0922a9abab",
        )

    mock_read.assert_called_once_with(225106397622015, 20, 30)


@pytest.mark.asyncio
async def test_bleak_client_get_services_and_read_write(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test getting client services via the bleak wrapper and read/write a GATT char."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    bleak_client = BleakClient(
        ble_device, backend=partial(ESPHomeClient, client_data=client_data)
    )
    client: ESPHomeClient = bleak_client._backend
    client._is_connected = True
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await bleak_client.get_services()

    assert services is not None

    char2 = bleak_client.services.get_characteristic(
        "090b7847-e12b-09a8-b04b-8e0922a9abab"
    )
    assert char2 is not None
    assert char2.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char2.properties == ["read", "write"]
    assert char2.handle == 20

    char3 = bleak_client.services.get_characteristic(
        UUID("090b7847-e12b-09a8-b04b-8e0922a9abab")
    )
    assert char3 is not None
    assert char3.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char3.properties == ["read", "write"]
    assert char3.handle == 20

    char = client._resolve_characteristic(
        char_specifier="090b7847-e12b-09a8-b04b-8e0922a9abab",
    )
    assert char is not None
    assert char.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char.properties == ["read", "write"]
    assert char.handle == 20

    with patch.object(
        client._client,
        "bluetooth_gatt_write",
    ) as mock_write:
        await bleak_client.write_gatt_char(
            "090b7847-e12b-09a8-b04b-8e0922a9abab",
            b"test",
            True,
        )

    mock_write.assert_called_once_with(225106397622015, 20, b"test", True)

    with patch.object(
        client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await bleak_client.read_gatt_char(
            "090b7847-e12b-09a8-b04b-8e0922a9abab",
        )

    mock_read.assert_called_once_with(225106397622015, 20, 30)


@pytest.mark.asyncio
async def test_bleak_client_cached_get_services_and_read_write(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test cached client services via the bleak wrapper and read/write a GATT char."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    bleak_client = BleakClient(
        ble_device, backend=partial(ESPHomeClient, client_data=client_data)
    )
    client: ESPHomeClient = bleak_client._backend
    client._is_connected = True
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=esphome_bluetooth_gatt_services,
    ):
        services = await bleak_client.get_services(dangerous_use_bleak_cache=True)

    assert services is not None

    services2 = await bleak_client.get_services(dangerous_use_bleak_cache=True)
    assert services2 is not None
    assert services2 == services

    char2 = bleak_client.services.get_characteristic(
        "090b7847-e12b-09a8-b04b-8e0922a9abab"
    )
    assert char2 is not None
    assert char2.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char2.properties == ["read", "write"]
    assert char2.handle == 20

    char3 = bleak_client.services.get_characteristic(
        UUID("090b7847-e12b-09a8-b04b-8e0922a9abab")
    )
    assert char3 is not None
    assert char3.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char3.properties == ["read", "write"]
    assert char3.handle == 20

    char = client._resolve_characteristic(
        char_specifier="090b7847-e12b-09a8-b04b-8e0922a9abab",
    )
    assert char is not None
    assert char.uuid == "090b7847-e12b-09a8-b04b-8e0922a9abab"
    assert char.properties == ["read", "write"]
    assert char.handle == 20

    with patch.object(
        client._client,
        "bluetooth_gatt_write",
    ) as mock_write:
        await bleak_client.write_gatt_char(
            "090b7847-e12b-09a8-b04b-8e0922a9abab",
            b"test",
            True,
        )

    mock_write.assert_called_once_with(225106397622015, 20, b"test", True)

    with patch.object(
        client._client,
        "bluetooth_gatt_read",
    ) as mock_read:
        await bleak_client.read_gatt_char(
            "090b7847-e12b-09a8-b04b-8e0922a9abab",
        )

    mock_read.assert_called_once_with(225106397622015, 20, 30)


@pytest.mark.asyncio
async def test_bleak_client_connect(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test connect and disconnect when connection slots are available."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    bleak_client = BleakClient(
        ble_device, backend=partial(ESPHomeClient, client_data=client_data)
    )
    client: ESPHomeClient = bleak_client._backend
    client._bluetooth_device.ble_connections_free = 10
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        # Mock connected with MTU of 23 and error code 0
        callback(True, 23, 0)
        await task

    assert client.is_connected
    assert client._mtu == 23
    with patch.object(
        client._client,
        "bluetooth_device_disconnect",
    ) as mock_disconnect:
        await client.disconnect()

    mock_disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bleak_client_connect_wait_for_connection_slot(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test connect and disconnect when connection slots are not available."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    bleak_client = BleakClient(
        ble_device, backend=partial(ESPHomeClient, client_data=client_data)
    )
    client: ESPHomeClient = bleak_client._backend
    client._bluetooth_device.ble_connections_free = 0
    with (
        patch.object(
            client._client,
            "bluetooth_device_connect",
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        mock_connect.assert_not_called()
        client._bluetooth_device.async_update_ble_connection_limits(10, 10, [])
        await asyncio.sleep(0)
        callback = mock_connect.call_args_list[0][0][1]
        # Mock connected with MTU of 23 and error code 0
        callback(True, 23, 0)
        await task

    assert client.is_connected
    assert client._mtu == 23
    with patch.object(
        client._client,
        "bluetooth_device_disconnect",
    ) as mock_disconnect:
        await client.disconnect()

    mock_disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_bleak_client_connect_wait_for_connection_slot_timeout(
    client_data: ESPHomeClientData,
    esphome_bluetooth_gatt_services: ESPHomeBluetoothGATTServices,
) -> None:
    """Test connect and disconnect when connection slots wait times out."""
    ble_device = generate_ble_device(
        "CC:BB:AA:DD:EE:FF", details={"source": ESP_MAC_ADDRESS, "address_type": 1}
    )

    bleak_client = BleakClient(
        ble_device, backend=partial(ESPHomeClient, client_data=client_data)
    )
    client: ESPHomeClient = bleak_client._backend
    client._bluetooth_device.ble_connections_free = 0
    with (
        pytest.raises(asyncio.TimeoutError),
        patch.object(
            client._client,
            "bluetooth_device_connect",
        ) as mock_connect,
        patch.object(
            client._client,
            "bluetooth_gatt_get_services",
            return_value=esphome_bluetooth_gatt_services,
        ),
        patch("bleak_esphome.backend.client.CONNECT_FREE_SLOT_TIMEOUT", 0.0001),
    ):
        task = asyncio.create_task(bleak_client.connect(dangerous_use_bleak_cache=True))
        await asyncio.sleep(0)
        mock_connect.assert_not_called()
        await task

    assert not client.is_connected
