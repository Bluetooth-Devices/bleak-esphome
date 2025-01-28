from unittest.mock import AsyncMock, Mock, patch

import pytest
from aioesphomeapi import (
    APIClient,
    APIVersion,
    DeviceInfo,
    ReconnectLogic,
)
from bleak_retry_connector import BleakSlotManager
from bluetooth_adapters import BluetoothAdapters
from habluetooth import (
    BluetoothManager,
    set_manager,
)
from zeroconf import Zeroconf


@pytest.fixture(scope="session", autouse=True)
def manager():
    slot_manager = BleakSlotManager()
    bluetooth_adapters = BluetoothAdapters()
    set_manager(BluetoothManager(bluetooth_adapters, slot_manager))


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return the default mocked device info."""
    return DeviceInfo(
        uses_password=False,
        name="test",
        legacy_bluetooth_proxy_version=0,
        # ESPHome mac addresses are UPPER case
        mac_address="11:22:33:44:55:AA",
        esphome_version="1.0.0",
    )


class BaseMockReconnectLogic(ReconnectLogic):
    """Mock ReconnectLogic."""

    def stop_callback(self) -> None:
        """Stop the reconnect logic."""
        # For the purposes of testing, we don't want to wait
        # for the reconnect logic to finish trying to connect
        self._cancel_connect("forced disconnect from test")
        self._is_stopped = True

    async def stop(self) -> None:
        """Stop the reconnect logic."""
        self.stop_callback()


@pytest.fixture
def mock_client(mock_device_info: DeviceInfo) -> APIClient:
    """Mock APIClient."""
    mock_client = Mock(spec=APIClient)

    def mock_constructor(
        address: str,
        port: int,
        password: str | None,
        *,
        client_info: str = "aioesphomeapi",
        keepalive: float = 15.0,
        zeroconf_instance: Zeroconf = None,
        noise_psk: str | None = None,
        expected_name: str | None = None,
    ) -> APIClient:
        """Fake the client constructor."""
        mock_client.host = address
        mock_client.port = port
        mock_client.password = password
        mock_client.zeroconf_instance = zeroconf_instance
        mock_client.noise_psk = noise_psk
        return mock_client

    mock_client.side_effect = mock_constructor
    mock_client.device_info = AsyncMock(return_value=mock_device_info)
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.list_entities_services = AsyncMock(return_value=([], []))
    mock_client.address = "127.0.0.1"
    mock_client.api_version = APIVersion(99, 99)

    with (
        patch(
            "aioesphomeapi.ReconnectLogic",
            BaseMockReconnectLogic,
        ),
        patch("aioesphomeapi.APIClient", mock_client),
    ):
        yield mock_client
