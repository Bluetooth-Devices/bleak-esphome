import pytest
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


@pytest.mark.parametrize(
    "adv",
    [
        BluetoothLERawAdvertisementsResponse(
            advertisements=[
                BluetoothLERawAdvertisement(
                    address=70425022386336,
                    address_type=1,
                    rssi=-71,
                    data=bytes.fromhex("02011a020a0c0bff4c001006421dd63f4f78"),
                ),
                BluetoothLERawAdvertisement(
                    address=135329407497497,
                    address_type=1,
                    rssi=-81,
                    data=bytes.fromhex(
                        "0201020909613235626430643911070000cdc4c6eaeeb6c845adad33b3d639"
                    ),
                ),
                BluetoothLERawAdvertisement(
                    address=277557927228479,
                    address_type=1,
                    rssi=-66,
                    data=bytes.fromhex("0201050716feff0900ff10"),
                ),
                BluetoothLERawAdvertisement(
                    address=114190995661889,
                    address_type=1,
                    rssi=-96,
                    data=bytes.fromhex("02011a0eff4c000f059000c962d610022004020a00"),
                ),
                BluetoothLERawAdvertisement(
                    address=261602360644300,
                    address_type=1,
                    rssi=-87,
                    data=bytes.fromhex(
                        "020104030307fe14ffa705060012702500ca00000800000000000000020a00"
                    ),
                ),
                BluetoothLERawAdvertisement(
                    address=211748016838317,
                    address_type=0,
                    rssi=-66,
                    data=bytes.fromhex("02011a020a0c0aff4c0010050a1484face"),
                ),
            ]
        ),
        BluetoothLERawAdvertisementsResponse(
            advertisements=[
                BluetoothLERawAdvertisement(
                    address=114037465385277,
                    address_type=1,
                    rssi=-84,
                    data=bytes.fromhex(
                        "02011a17ff4c0009081333c0a86b451b5813084a100a5d79d40b00"
                    ),
                ),
                BluetoothLERawAdvertisement(
                    address=9049263188781,
                    address_type=0,
                    rssi=-53,
                    data=bytes.fromhex(
                        "0201060303121810094c4f4f4b696e5f39384633333046330319c103"
                    ),
                ),
            ]
        ),
        BluetoothLERawAdvertisementsResponse(
            advertisements=[
                BluetoothLERawAdvertisement(
                    address=116435956320074,
                    address_type=1,
                    rssi=-83,
                    data=bytes.fromhex("02011a0eff4c000f05900041434b10022504020a00"),
                ),
                BluetoothLERawAdvertisement(
                    address=9049263190633,
                    address_type=0,
                    rssi=-77,
                    data=bytes.fromhex(
                        "0201060303121810094c4f4f4b696e5f39384633333230440319c103"
                    ),
                ),
                BluetoothLERawAdvertisement(
                    address=132613642173324,
                    address_type=0,
                    rssi=-91,
                    data=bytes.fromhex(
                        "02010616ff4c00063100426ae1cd514f060028000502f248880204084d3130"
                    ),
                ),
            ]
        ),
    ],
    ids=["adv1", "adv2", "adv3"],
)
def test_scanner_real_adv_data(
    benchmark: BenchmarkFixture, adv: BluetoothLERawAdvertisementsResponse
) -> None:
    """Benchmark the async_on_advertisement method with real advertisements."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    scanner = ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)

    @benchmark
    def _benchmark():
        for _ in range(1000):
            scanner.async_on_raw_advertisements(adv)
