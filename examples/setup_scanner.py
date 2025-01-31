import asyncio
import logging

import aioesphomeapi
import habluetooth
from bleak_retry_connector import BleakSlotManager
from bluetooth_adapters import BluetoothAdapters
from zeroconf.asyncio import AsyncZeroconf

import bleak_esphome

ESPHOME_DEVICE = "kitchenalexproxy.local."


async def setup_hablueooth() -> None:
    """Setup the habluetooth manager."""
    slot_manager = BleakSlotManager()
    bluetooth_adapters = BluetoothAdapters()
    manager = habluetooth.BluetoothManager(bluetooth_adapters, slot_manager)
    habluetooth.set_manager(manager)
    await manager.async_setup()


async def setup_api_connection(
    aiozc: AsyncZeroconf,
) -> tuple[aioesphomeapi.ReconnectLogic, aioesphomeapi.APIClient]:
    """Setup the API connection."""
    cli = aioesphomeapi.APIClient(
        address=ESPHOME_DEVICE,
        port=6052,
        password=None,
    )

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

    return reconnect_logic, cli


async def run_application(cli: aioesphomeapi.APIClient) -> None:
    """Test application here."""
    event = asyncio.Event()
    await event.wait()


async def run() -> None:
    """Run the main application."""
    try:
        aiozc = AsyncZeroconf()
        await setup_hablueooth()
        reconnect_logic, cli = await setup_api_connection(aiozc)
        await run_application(cli)
    finally:
        await reconnect_logic.stop()
        await cli.disconnect()
        await aiozc.async_close()


logging.basicConfig(level=logging.DEBUG)

asyncio.run(run())
