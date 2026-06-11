"""
High-level example: connect to a BLE device through a proxy and read GATT.

``setup_scanner.py`` shows how to bring an ``APIConnectionManager`` up and let
``bleak`` *discover* advertisements. This example takes the next step — the one
the whole library exists for — and opens a *GATT connection* to a specific
device, routed transparently through whichever proxy can reach it.

``bleak_esphome`` never appears in the connect/read code: once a scanner is
registered, ``habluetooth`` routes a plain ``bleak.BleakClient`` to the right
proxy. Replace ``ESPHOME_DEVICES`` and ``TARGET_ADDRESS`` with your hardware
before running. This talks to real hardware, so it cannot run in CI.

Proxy caveats worth knowing (see ``docs/usage.md`` for the full list):

* A device is connectable only if a proxy advertising ``ACTIVE_CONNECTIONS``
  heard it. Scan-only proxies surface advertisements but cannot open a link.
* Connection slots are finite. ``connect()`` waits for a free slot and raises
  ``TimeoutError`` if none frees within the timeout — so disconnect when done
  (the ``async with`` block below does this for you).
"""

from __future__ import annotations

import asyncio
import logging

import bleak
import habluetooth

from bleak_esphome import APIConnectionManager, ESPHomeDeviceConfig

# Give the proxy time to hear the target device advertise before connecting.
SCAN_SECONDS = 10
# Address (or UUID on macOS) of the BLE device you want to talk to.
TARGET_ADDRESS = "AA:BB:CC:DD:EE:FF"
# Battery Service / Battery Level characteristic — swap for your own UUID.
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# One or more ESPHome Bluetooth proxies to bring online.
ESPHOME_DEVICES: list[ESPHomeDeviceConfig] = [
    {
        "address": "XXXX.local.",
        "noise_psk": None,
    },
]


async def read_battery_level(address: str) -> int:
    """
    Connect to ``address`` through the proxy and read its battery level.

    ``find_device_by_address`` returns ``None`` until the proxy has heard the
    device advertise, so a real app would retry; here we surface a clear error
    instead.
    """
    device = await bleak.BleakScanner.find_device_by_address(address)
    if device is None:
        raise RuntimeError(f"{address} not found — is it advertising in range?")

    async with bleak.BleakClient(device) as client:
        payload = await client.read_gatt_char(BATTERY_LEVEL_UUID)
        return payload[0]


async def run() -> None:
    """Bring proxies up, read one device's battery level, then tear down."""
    connections = [APIConnectionManager(device) for device in ESPHOME_DEVICES]
    # The host-side manager must exist before any scanner is registered.
    await habluetooth.BluetoothManager().async_setup()
    try:
        await asyncio.gather(*(conn.start() for conn in connections))
        # Let the proxies hear advertisements before we look up the device.
        await asyncio.sleep(SCAN_SECONDS)

        level = await read_battery_level(TARGET_ADDRESS)
        print(f"{TARGET_ADDRESS} battery level: {level}%")
    finally:
        await asyncio.gather(*(conn.stop() for conn in connections))


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())
