"""Importable helpers and constants for ``tests/backend``."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from bleak import BleakClient
from bleak.backends.device import BLEDevice

from bleak_esphome.backend.client import ESPHomeClient, ESPHomeClientData

from .. import generate_ble_device

if TYPE_CHECKING:
    from collections.abc import Iterator

    from aioesphomeapi import ESPHomeBluetoothGATTServices
    from bleak.backends.service import BleakGATTServiceCollection

ESP_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
ESP_NAME = "proxy"
BLE_ADDRESS = "CC:BB:AA:DD:EE:FF"


def make_ble_device() -> BLEDevice:
    """Return the standard remote BLE device used by tests."""
    return generate_ble_device(
        BLE_ADDRESS,
        details={"source": ESP_MAC_ADDRESS, "address_type": 1},
    )


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
    return ESPHomeClient(make_ble_device(), client_data=client_data)


def make_bleak_client(
    client_data: ESPHomeClientData,
    *,
    pair: bool = False,
    free_slots: int = 10,
) -> tuple[BleakClient, ESPHomeClient]:
    """
    Build a ``BleakClient`` plus its bound ``ESPHomeClient`` backend.

    The backend's ``ble_connections_free`` is pre-set to ``free_slots`` so
    callers can drive ``connect()`` without manually wiring connection limits.
    """
    bleak_client = BleakClient(
        make_ble_device(),
        backend=_make_client_backend(client_data),
        pair=pair,
    )
    backend: ESPHomeClient = bleak_client._backend
    backend._bluetooth_device.ble_connections_free = free_slots
    return bleak_client, backend


@contextmanager
def patch_get_services(
    client: ESPHomeClient,
    payload: ESPHomeBluetoothGATTServices,
) -> Iterator[None]:
    """Patch the proxy's ``bluetooth_gatt_get_services`` to return ``payload``."""
    with patch.object(
        client._client,
        "bluetooth_gatt_get_services",
        return_value=payload,
    ):
        yield


async def fetch_services(
    client: ESPHomeClient,
    payload: ESPHomeBluetoothGATTServices,
    *,
    dangerous_use_bleak_cache: bool = False,
) -> BleakGATTServiceCollection:
    """Patch the GATT services call and return the resolved service collection."""
    with patch_get_services(client, payload):
        return await client._get_services(
            dangerous_use_bleak_cache=dangerous_use_bleak_cache,
        )
