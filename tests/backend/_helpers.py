"""Importable helpers and constants for ``tests/backend``."""

from __future__ import annotations

from typing import Any

from bleak.backends.device import BLEDevice

from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData

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
