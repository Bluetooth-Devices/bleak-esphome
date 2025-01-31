(usage)=

# Usage

Assuming that you've followed the {ref}`installations steps <installation>`, you're now ready to use this package.

Example usage with `bleak`:

```python
import asyncio
import logging
from collections.abc import Callable

import habluetooth
from aioesphomeapi import APIClient, ReconnectLogic

import bleak_esphome

ESPHOME_DEVICE = "XXXX.local."
NOISE_PSK = ""


async def setup_api_connection() -> tuple[ReconnectLogic, APIClient]:
    """Setup the API connection."""
    args = {"address": ESPHOME_DEVICE, "port": 6053, "password": None}
    if NOISE_PSK:
        args["noise_psk"] = NOISE_PSK
    cli = APIClient(**args)
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
    reconnect_logic: ReconnectLogic | None = None
    cli: APIClient | None = None
    try:
        await habluetooth.BluetoothManager().async_setup()
        reconnect_logic, cli = await setup_api_connection()
        await run_application(cli)
    finally:
        if reconnect_logic is not None:
            await reconnect_logic.stop()
        if cli is not None:
            await cli.disconnect()


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())
```
