(usage)=

# Usage

Assuming that you've followed the {ref}`installations steps <installation>`, you're now ready to use this package.

Example usage with `bleak`:

```python
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TypedDict

import habluetooth
from aioesphomeapi import APIClient, ReconnectLogic

import bleak_esphome


class ESPHomeDeviceConfig(TypedDict):
    """Configuration for an ESPHome device."""

    address: str
    noise_psk: str | None


# An unlimited number of devices can be added here
ESPHOME_DEVICES: list[ESPHomeDeviceConfig] = [
    {
        "address": "XXXX.local.",
        "noise_psk": None,
    },
    {
        "address": "YYYY.local.",
        "noise_psk": None,
    },
]


async def setup_api_connection(
    address: str, noise_psk: str | None = None
) -> tuple[ReconnectLogic, APIClient]:
    """Setup the API connection."""
    cli = APIClient(address=address, port=6053, password=None, noise_psk=noise_psk)
    unregister_scanner: Callable[[], None] | None = None

    async def on_disconnect(expected_disconnect: bool) -> None:
        nonlocal unregister_scanner
        if unregister_scanner is not None:
            unregister_scanner()
            unregister_scanner = None

    async def on_connect() -> None:
        nonlocal unregister_scanner
        device_info = await cli.device_info()
        client_data = bleak_esphome.connect_scanner(cli, device_info, True)
        scanner = client_data.scanner
        assert scanner is not None  # noqa: S101
        scanner.async_setup()
        unregister_scanner = habluetooth.get_manager().async_register_scanner(scanner)

    reconnect_logic = ReconnectLogic(
        client=cli,
        on_disconnect=on_disconnect,
        on_connect=on_connect,
    )
    await reconnect_logic.start()

    return reconnect_logic, cli


async def run_application(cli: APIClient) -> None:
    """Test application here."""
    import bleak  # noqa

    # Use bleak normally here

    # Wait forever
    event = asyncio.Event()
    await event.wait()


async def run() -> None:
    """Run the main application."""
    esphome_connections: list[tuple[ReconnectLogic, APIClient]] = []
    reconnect_logic: ReconnectLogic | None = None
    cli: APIClient | None = None
    try:
        await habluetooth.BluetoothManager().async_setup()
        for device in ESPHOME_DEVICES:
            esphome_connections.append(await setup_api_connection(
                device["address"], device["noise_psk"]
            ))
        await run_application(cli)
    finally:
        for reconnect_logic, cli in esphome_connections:
            await reconnect_logic.stop()
            await cli.disconnect()


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())
```
