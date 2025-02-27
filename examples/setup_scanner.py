from __future__ import annotations

import asyncio
import logging

import habluetooth

from bleak_esphome import APIConnectionManager, ESPHomeDeviceConfig

CONNECTION_TIMEOUT = 5

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


async def example_app() -> None:
    """Example application here."""
    import bleak

    # Use bleak normally here
    devices = await bleak.BleakScanner.discover(return_adv=True)
    for d, a in devices.values():
        print()
        print(d)
        print("-" * len(str(d)))
        print(a)

    # Wait forever
    await asyncio.Event().wait()


async def run() -> None:
    """Run the main application."""
    connections = [APIConnectionManager(device) for device in ESPHOME_DEVICES]
    await habluetooth.BluetoothManager().async_setup()
    try:
        await asyncio.wait(
            (asyncio.create_task(conn.start()) for conn in connections),
            timeout=CONNECTION_TIMEOUT,
        )
        await example_app()
    finally:
        await asyncio.gather(*(conn.stop() for conn in connections))


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())
