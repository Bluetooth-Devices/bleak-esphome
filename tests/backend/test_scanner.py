from habluetooth import (
    BaseHaRemoteScanner,
    HaBluetoothConnector,
)

from bleak_esphome.backend.client import ESPHomeClientData
from bleak_esphome.backend.scanner import ESPHomeScanner

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


def test_scanner():
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)
    assert isinstance(scanner, BaseHaRemoteScanner)
