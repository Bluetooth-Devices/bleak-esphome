from aioesphomeapi import (
    BluetoothLERawAdvertisement,
    BluetoothLERawAdvertisementsResponse,
)
from habluetooth import (
    HaBluetoothConnector,
)
from pytest_codspeed import BenchmarkFixture

from bleak_esphome.backend.client import ESPHomeClientData
from bleak_esphome.backend.scanner import ESPHomeScanner

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"


def test_scanner_async_on_advertisement(benchmark: BenchmarkFixture) -> None:
    """Benchmark the async_on_advertisement method with two advertisements."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)
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

    @benchmark
    def _benchmark():
        for _ in range(1000):
            scanner.async_on_raw_advertisements(adv)


def test_scanner_async_on_advertisement_six(benchmark: BenchmarkFixture) -> None:
    """Benchmark the async_on_advertisement method with six advertisements."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)
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
            BluetoothLERawAdvertisement(
                address=246965243285493,
                rssi=-83,
                address_type=1,
                data=b"\x02\x01\x1a\x1b\xffu\x00B\x04\x01\x01o\xe0\x8d\x17\xe7\x0f\xf3\xe2\x8d\x17\xe7\x0f\xf2(\x00\x00\x00\x00\x00\x00",
            ),
            BluetoothLERawAdvertisement(
                address=246965243285494,
                rssi=-84,
                address_type=1,
                data=b"\x02\x01\x1a\x1b\xffu\x00B\x04\x01\x01o\xe0\x8d\x17\xe7\x0f\xf3\xe2\x8d\x17\xe7\x0f\xf2(\x00\x00\x00\x00\x00\x00",
            ),
            BluetoothLERawAdvertisement(
                address=246965243285495,
                rssi=-81,
                address_type=1,
                data=b"\x02\x01\x1a\x1b\xffu\x00B\x04\x01\x01o\xe0\x8d\x17\xe7\x0f\xf3\xe2\x8d\x17\xe7\x0f\xf2(\x00\x00\x00\x00\x00\x00",
            ),
            BluetoothLERawAdvertisement(
                address=246965243285496,
                rssi=-53,
                address_type=1,
                data=b"\x02\x01\x1a\x1b\xffu\x00B\x04\x01\x01o\xe0\x8d\x17\xe7\x0f\xf3\xe2\x8d\x17\xe7\x0f\xf2(\x00\x00\x00\x00\x00\x00",
            ),
        ]
    )

    @benchmark
    def _benchmark():
        for _ in range(1000):
            scanner.async_on_raw_advertisements(adv)
