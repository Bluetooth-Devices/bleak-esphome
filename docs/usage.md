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


async def example_app() -> None:
    """Example application here."""
    import bleak

    await asyncio.sleep(5) # Give time for advertisements to be received

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
```

## Handling start cancellation

`APIConnectionManager.start()` blocks until the first successful connection
attempt completes. If `stop()` is called while a `start()` task is still
awaiting that first connection, `start()` raises
`bleak_esphome.ESPHomeStartAborted` instead of leaking a bare
`asyncio.CancelledError`. The typed exception lets `TaskGroup` and
`asyncio.timeout()` callers tell "we asked it to stop" apart from "the
surrounding task was actually cancelled":

```python
from bleak_esphome import APIConnectionManager, ESPHomeStartAborted

manager = APIConnectionManager({"address": "device.local.", "noise_psk": None})
start_task = asyncio.create_task(manager.start())
try:
    await start_task
except ESPHomeStartAborted:
    # stop() was called before the first connection completed; nothing
    # else to clean up here.
    pass
```

The example above uses `asyncio.wait`, which keeps each task's exception on
the task object rather than re-raising — you only see `ESPHomeStartAborted`
if you later `await` the task or call `task.result()`.

## Extension Methods

`ESPHomeClient` provides extension methods beyond the standard `BleakClient` interface. These are typically called via `BleakClientWithServiceCache` from `bleak-retry-connector`, which forwards them to `ESPHomeClient`.

### clear_cache

```python
async def clear_cache(self) -> bool
```

Clears the GATT services cache on both the local side and the ESP32 device. Useful when a connected device's firmware has been updated or services have changed.

Returns `True` if the cache was successfully cleared, `False` otherwise.

Requires the `CACHE_CLEARING` feature flag. If the ESPHome firmware is too old to support on-device cache clearing, only the local memory cache is cleared and a warning is logged.

```python
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

client = await establish_connection(
    BleakClientWithServiceCache, device, name="MyDevice"
)

# If characteristics are missing after a firmware update, clear cache
await client.clear_cache()
await client.disconnect()
```

### set_connection_params

```python
async def set_connection_params(
    self,
    min_interval: int,
    max_interval: int,
    latency: int,
    timeout: int,
) -> None
```

Sets BLE connection parameters on the connected device via the ESP32 proxy. The ESP32 calls `esp_ble_gap_update_conn_params()` to request new parameters from the peripheral.

This is useful for "Always Connected" devices where battery conservation is important — switching from fast intervals (~7.5ms) to slow intervals (e.g., 1000ms) after the initial data sync can significantly reduce power consumption.

Parameters are in BLE units:

- **min_interval** / **max_interval**: Connection interval in units of 1.25ms (e.g., 800 = 1000ms)
- **latency**: Number of connection events the peripheral can skip (typically 0)
- **timeout**: Supervision timeout in units of 10ms (e.g., 600 = 6000ms)

Requires the `CONNECTION_PARAMS_SETTING` feature flag. If the ESPHome firmware is too old, a warning is logged with the current ESPHome version.

```python
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

client = await establish_connection(
    BleakClientWithServiceCache, device, name="MyDevice"
)

# After initial sync, switch to slow intervals to save battery
await client.set_connection_params(
    min_interval=800,  # 1000ms
    max_interval=800,  # 1000ms
    latency=0,
    timeout=600,  # 6000ms
)
```
