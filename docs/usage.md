(usage)=

# Usage

Assuming that you've followed the {ref}`installations steps <installation>`, you're now ready to use this package.

Example usage with `bleak`:

```python
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


async def run_application() -> None:
    """Test application here."""
    import bleak  # noqa

    # Use bleak normally here

    # Wait forever
    event = asyncio.Event()
    await event.wait()


async def run() -> None:
    """Run the main application."""
    connections = [APIConnectionManager(device) for device in ESPHOME_DEVICES]
    await habluetooth.BluetoothManager().async_setup()
    try:
        await asyncio.wait(
            (asyncio.create_task(conn.start()) for conn in connections),
            timeout=CONNECTION_TIMEOUT,
        )
        await run_application()
    finally:
        await asyncio.gather(*(conn.stop() for conn in connections))


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())
```
