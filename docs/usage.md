(usage)=

# Usage

Assuming that you've followed the {ref}`installations steps <installation>`, you're now ready to use this package.

Example usage with `bleak`:

```python
import asyncio
import logging

import aioesphomeapi
import habluetooth
from bleak_retry_connector import BleakSlotManager
from bluetooth_adapters import get_adapters
from zeroconf.asyncio import AsyncZeroconf

import bleak_esphome

ESPHOME_DEVICE = "XXXX.local."
NOISE_PSK = ""


async def setup_api_connection(
    aiozc: AsyncZeroconf,
) -> tuple[aioesphomeapi.ReconnectLogic, aioesphomeapi.APIClient]:
    """Setup the API connection."""
    args = {
        "address": ESPHOME_DEVICE,
        "port": 6053,
        "password": None,
    }
    if NOISE_PSK:
        args["noise_psk"] = NOISE_PSK
    cli = aioesphomeapi.APIClient(**args)

    async def on_disconnect(expected_disconnect: bool) -> None:
        pass

    async def on_connect() -> None:
        device_info = await cli.device_info()
        bleak_esphome.connect_scanner(cli, device_info, True)

    reconnect_logic = aioesphomeapi.ReconnectLogic(
        client=cli,
        on_disconnect=on_disconnect,
        on_connect=on_connect,
        zeroconf_instance=aiozc,
    )
    await reconnect_logic.start()

    return reconnect_logic, cli


async def run_application(cli: aioesphomeapi.APIClient) -> None:
    """Test application here."""
    import bleak  # noqa

    # Use bleak normally here

    # Wait forever
    event = asyncio.Event()
    await event.wait()


async def run() -> None:
    """Run the main application."""
    reconnect_logic: aioesphomeapi.ReconnectLogic | None = None
    cli: aioesphomeapi.APIClient | None = None
    aiozc: AsyncZeroconf | None = None
    try:
        aiozc = AsyncZeroconf()
        await habluetooth.BluetoothManager().async_setup()
        reconnect_logic, cli = await setup_api_connection(aiozc)
        await run_application(cli)
    finally:
        if reconnect_logic is not None:
            await reconnect_logic.stop()
        if cli is not None:
            await cli.disconnect()
        if aiozc is not None:
            await aiozc.async_close()


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())

```
