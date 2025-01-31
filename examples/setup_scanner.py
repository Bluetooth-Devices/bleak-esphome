import asyncio
import logging

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

    async def on_disconnect(expected_disconnect: bool) -> None:
        pass

    async def on_connect() -> None:
        device_info = await cli.device_info()
        bleak_esphome.connect_scanner(cli, device_info, True)

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
