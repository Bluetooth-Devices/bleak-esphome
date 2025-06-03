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
    BaseHaRemoteScanner,
    BluetoothScanningMode,
    HaBluetoothConnector,
    get_manager,
)

from bleak_esphome.backend.client import ESPHomeClientData
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
