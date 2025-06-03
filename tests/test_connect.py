import pytest
from aioesphomeapi import APIClient

from bleak_esphome.connect import connect_scanner


@pytest.mark.asyncio
async def test_connect(mock_client: APIClient) -> None:
    """Test the connect_scanner function."""
    device_info = await mock_client.device_info()
    scanner = connect_scanner(mock_client, device_info, available=True)
    assert scanner is not None
    assert (
        scanner.device_info.bluetooth_mac_address == device_info.bluetooth_mac_address
    )
    assert scanner.client is mock_client
