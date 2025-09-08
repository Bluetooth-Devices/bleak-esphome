import pytest
from aioesphomeapi import (
    APIClient,
    BluetoothLERawAdvertisement,
    BluetoothLERawAdvertisementsResponse,
    BluetoothScannerMode,
    BluetoothScannerStateResponse,
)
from bluetooth_data_tools import int_to_bluetooth_address
from habluetooth import (
    Allocations,
    BaseHaRemoteScanner,
    BluetoothScanningMode,
    HaBluetoothConnector,
    get_manager,
)

from bleak_esphome.backend.client import ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


@pytest.fixture
def scanner() -> ESPHomeScanner:
    """Fixture to create an ESPHomeScanner instance."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    return ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)


def test_scanner(scanner: ESPHomeScanner) -> None:
    assert isinstance(scanner, BaseHaRemoteScanner)


def test_scanner_async_on_advertisement(scanner: ESPHomeScanner) -> None:
    adv = BluetoothLERawAdvertisementsResponse(
        advertisements=[
            BluetoothLERawAdvertisement(
                address=261602360644300,
                rssi=-96,
                address_type=1,
                data=b"\x02\x01\x04\x03\x03\x07\xfe\x18\xff\x97\x05\x06\x00\x16p%\x00\xca\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x02\n\x00",
            ),
            BluetoothLERawAdvertisement(
                address=246965243285491,
                rssi=-88,
                address_type=1,
                data=b"\x02\x01\x1a\x1b\xffu\x00B\x04\x01\x01o\xe0\x8d\x17\xe7\x0f\xf3\xe2\x8d\x17\xe7\x0f\xf2(\x00\x00\x00\x00\x00\x00",
            ),
        ]
    )
    scanner.async_on_raw_advertisements(adv)
    manager = get_manager()
    assert manager.async_last_service_info(
        int_to_bluetooth_address(261602360644300), True
    )
    assert manager.async_last_service_info(
        int_to_bluetooth_address(246965243285491), True
    )


def test_scanner_async_update_scanner_state(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    mock_client.subscribe_bluetooth_scanner_state(scanner.async_update_scanner_state)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            mode=BluetoothScannerMode.ACTIVE,
        )
    )
    assert scanner.current_mode == BluetoothScanningMode.ACTIVE
    assert scanner.requested_mode == BluetoothScanningMode.ACTIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.current_mode == BluetoothScanningMode.PASSIVE
    assert scanner.requested_mode == BluetoothScanningMode.PASSIVE
    scanner.async_update_scanner_state(BluetoothScannerStateResponse(mode=None))
    assert scanner.current_mode is None
    assert scanner.requested_mode is None


@pytest.mark.asyncio
async def test_scanner_get_allocations_no_device(scanner: ESPHomeScanner) -> None:
    """Test get_allocations returns None when no bluetooth device is set."""
    assert scanner.get_allocations() is None


@pytest.mark.asyncio
async def test_scanner_get_allocations_no_limit(scanner: ESPHomeScanner) -> None:
    """Test get_allocations returns None when device has no connection limit."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 0
    device.ble_connections_free = 0
    scanner.set_bluetooth_device(device)
    assert scanner.get_allocations() is None


@pytest.mark.asyncio
async def test_scanner_get_allocations_with_device(scanner: ESPHomeScanner) -> None:
    """Test get_allocations returns correct allocation info when device is set."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 3
    device.ble_connections_free = 2
    device.ble_allocations = [123456789]  # Example allocated address

    scanner.set_bluetooth_device(device)
    allocations = scanner.get_allocations()

    assert allocations is not None
    assert isinstance(allocations, Allocations)
    assert allocations.adapter == ESP_MAC_ADDRESS
    assert allocations.slots == 3
    assert allocations.free == 2
    assert allocations.allocated == [123456789]


@pytest.mark.asyncio
async def test_scanner_get_allocations_no_free_slots(scanner: ESPHomeScanner) -> None:
    """Test get_allocations when all slots are in use."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 2
    device.ble_connections_free = 0
    device.ble_allocations = [111111111, 222222222]

    scanner.set_bluetooth_device(device)
    allocations = scanner.get_allocations()

    assert allocations is not None
    assert allocations.adapter == ESP_MAC_ADDRESS
    assert allocations.slots == 2
    assert allocations.free == 0
    assert allocations.allocated == [111111111, 222222222]


@pytest.mark.asyncio
async def test_scanner_get_allocations_updates(scanner: ESPHomeScanner) -> None:
    """Test that get_allocations returns current values as they change."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 3
    device.ble_connections_free = 3
    device.ble_allocations = []

    scanner.set_bluetooth_device(device)

    # Initial state - all slots free
    allocations = scanner.get_allocations()
    assert allocations is not None
    assert allocations.free == 3
    assert allocations.allocated == []

    # Simulate a connection being made
    device.ble_connections_free = 2
    device.ble_allocations = [987654321]

    # Should return updated values
    allocations = scanner.get_allocations()
    assert allocations is not None
    assert allocations.free == 2
    assert allocations.allocated == [987654321]

    # Simulate another connection
    device.ble_connections_free = 1
    device.ble_allocations = [987654321, 876543210]

    allocations = scanner.get_allocations()
    assert allocations is not None
    assert allocations.free == 1
    assert allocations.allocated == [987654321, 876543210]
