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

## Feature Flag Reference

The proxy firmware advertises a `BluetoothProxyFeature` bitmask through
`DeviceInfo.bluetooth_proxy_feature_flags_compat(api_version)`. `bleak-esphome`
checks these flags before calling proxy-side APIs and degrades gracefully when
a flag is missing. The table below maps each public surface to the flag it
requires and what happens when the proxy firmware does not advertise it.

| Public surface                          | Required flag               | Behavior when flag is absent                                                                                                                                                                                                                                                      |
| --------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BleakClient.connect` / GATT operations | `ACTIVE_CONNECTIONS`        | The scanner is registered as non-connectable. Discovery still works; connect attempts are rejected by `bleak` before reaching this library.                                                                                                                                       |
| Decoded vs. raw advertisements          | `RAW_ADVERTISEMENTS`        | Falls back to `subscribe_bluetooth_le_advertisements` (proxy-side decoded) instead of `subscribe_bluetooth_le_raw_advertisements`. Both paths feed the same scanner.                                                                                                              |
| Scanner state / mode reporting          | `FEATURE_STATE_AND_MODE`    | `subscribe_bluetooth_scanner_state` is skipped; `current_mode` / `requested_mode` stay at their defaults. Connection-slot tracking is unaffected.                                                                                                                                 |
| `connect(dangerous_use_bleak_cache=…)`  | `REMOTE_CACHING`            | The cached-services hint sent to the proxy is forced off, so the proxy re-discovers services on every connect. `dangerous_use_bleak_cache` still hits the on-host LRU in `_get_services` when populated, and `start_notify` skips the CCCD write because the firmware handles it. |
| `BleakClient.pair` / `unpair`           | `PAIRING`                   | Raises `NotImplementedError("Pairing is not available in this version ESPHome; Upgrade the ESPHome version on the … device.")`.                                                                                                                                                   |
| `ESPHomeClient.clear_cache`             | `CACHE_CLEARING`            | Returns `True` after clearing only the on-host LRU caches; logs `"On device cache clear is not available with this ESPHome version; … Only memory cache will be cleared"`. No proxy round-trip.                                                                                   |
| `ESPHomeClient.set_connection_params`   | `CONNECTION_PARAMS_SETTING` | Silently returns after logging `"Setting connection parameters is not available with ESPHome version …; Upgrade the ESPHome version on the device"`. No exception is raised.                                                                                                      |

If a method appears to silently do nothing, check the proxy's reported feature
flags first — the warning is logged at WARNING level on the
`bleak_esphome.backend.client` logger.
