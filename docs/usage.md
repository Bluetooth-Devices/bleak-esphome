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

## Connecting to a device

Scanning is only half the story — the point of an active Bluetooth proxy is
to **connect** to a device and perform GATT operations (read, write, notify)
over the ESP32. Once a scanner is registered (the example above does this via
`APIConnectionManager`), you drive connections through `bleak` exactly as you
would with a local adapter. `bleak_esphome` never appears in this code: the
`habluetooth` manager transparently routes `bleak`'s `BleakClient` to the
proxy that can reach the target device.

```python
import bleak

# Battery Service / Battery Level characteristic.
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


async def read_battery_level(address: str) -> int:
    """Connect to a device through the proxy and read its battery level."""
    device = await bleak.BleakScanner.find_device_by_address(address)
    if device is None:
        raise RuntimeError(f"{address} not found — is it advertising in range?")

    async with bleak.BleakClient(device) as client:
        payload = await client.read_gatt_char(BATTERY_LEVEL_UUID)
        return payload[0]
```

A few proxy-specific things worth knowing:

- **Connectable proxies only.** A device is reachable for connections only if
  a proxy advertising the `ACTIVE_CONNECTIONS` feature flag has heard its
  advertisements. Scan-only proxies can surface the advertisement but not
  open a GATT link.
- **Connection slots are finite.** Each proxy exposes a fixed number of
  simultaneous active connections. When every slot is in use, a new
  `BleakClient.connect()` waits for one to free up and raises a
  `TimeoutError` if none does within the timeout. Disconnect clients you are
  done with so their slots return to the pool.
- **Pairing requires the `PAIRING` flag.** `BleakClient.pair()` / `unpair()`
  raise `NotImplementedError` against older firmware that does not advertise
  the flag. See the _Feature Flag Reference_ section below.

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

## Advanced: wiring `connect_scanner` directly

`APIConnectionManager` is the recommended entry point — it owns the
`APIClient`, drives `ReconnectLogic`, registers the scanner with
`habluetooth`, and tears everything down on `stop()`. Reach for
`connect_scanner` only when you already manage the `APIClient` lifecycle
yourself (for example, when integrating into a host that has its own
reconnect / discovery machinery).

`connect_scanner(cli, device_info, available)` wires an
`aioesphomeapi.APIClient` to an `ESPHomeScanner` + `ESPHomeClient` and
subscribes to the proxy's advertisement, scanner-state, and connection-slot
streams. It returns an `ESPHomeClientData` and leaves three jobs to the
caller:

1. Call `client_data.scanner.async_setup()` to attach the scanner to the
   running loop.
2. Register the scanner with the host-side Bluetooth manager (and
   un-register it when the ESP disconnects).
3. Fire every callback in `client_data.disconnect_callbacks` when the ESP
   disconnects, so `ESPHomeClient` instances drop their subscriptions.
   Iterate a snapshot of the set — each callback removes itself during
   cleanup.

```python
import habluetooth
from aioesphomeapi import APIClient

import bleak_esphome

cli = APIClient(address="device.local.", port=6053, password=None)
await cli.connect(login=True)
device_info = await cli.device_info()

client_data = bleak_esphome.connect_scanner(cli, device_info, available=True)
assert client_data.scanner is not None
client_data.scanner.async_setup()
unregister_scanner = habluetooth.get_manager().async_register_scanner(
    client_data.scanner
)

# Later, when the ESP disconnects:
for callback in list(client_data.disconnect_callbacks):
    callback()
unregister_scanner()
```

If you also want to override which `disconnect_callbacks` set is used —
for example, to share one set across several scanners — reassign
`client_data.disconnect_callbacks` **before** calling `async_setup()`.

## Scanning Modes

The proxy can scan in one of two firmware modes, and `habluetooth` adds a
third, host-side mode on top:

- **`PASSIVE`** — the proxy only listens for unsolicited advertisements.
  Lowest radio overhead, but advertisement payloads that a peripheral only
  emits in a _scan response_ (often the local name) are never seen.
- **`ACTIVE`** — the proxy sends scan requests and collects scan responses,
  so it picks up scan-response-only data at the cost of more airtime.
- **`AUTO`** — a `habluetooth`-only mode with no firmware equivalent. It maps
  to `PASSIVE` on the proxy; `habluetooth`'s auto-mode scheduler then opens
  brief `ACTIVE` windows on demand (via `async_request_active_window`) when a
  device actually needs scan-response data, and restores `PASSIVE` when the
  window closes. This gives most of `ACTIVE`'s coverage with most of
  `PASSIVE`'s efficiency.

The modes live in `habluetooth.BluetoothScanningMode`.

### Driving the mode

Once a scanner is registered with the host-side
`habluetooth.BluetoothManager`, the manager drives the mode for you — you
normally don't call anything. When you manage the scanner yourself (see
_Advanced: wiring `connect_scanner` directly_ above), pin a mode explicitly
with `async_set_scanning_mode`:

```python
from habluetooth import BluetoothScanningMode

# client_data is the result of bleak_esphome.connect_scanner(...)
scanner = client_data.scanner
assert scanner is not None

scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
```

`async_set_scanning_mode` is synchronous: it records the intent, updates
`requested_mode`, and queues the firmware request on the bound `APIClient`.
Once called, `requested_mode` is no longer overwritten by incoming firmware
state updates — your pinned intent wins. The call is a no-op against the
firmware if no `APIClient` has been bound (the proxy lacks
`FEATURE_STATE_AND_MODE`); the local intent is still recorded.

### Reading the configured firmware mode

`scanner.configured_mode` reports the proxy's last firmware-reported
_configured_ mode (`ACTIVE` / `PASSIVE`, or `None` before the first state
update). It's intended for one-shot migration logic at setup — for example,
"if the proxy was configured `ACTIVE`, switch the host option to `AUTO`".

Caveat: the underlying proto field shipped in ESPHome 2025.9.
`FEATURE_STATE_AND_MODE` firmware older than that leaves it unset, which
proto3 decodes as the default `PASSIVE` — indistinguishable from an explicit
`PASSIVE` configuration.

All of the above requires the proxy to advertise `FEATURE_STATE_AND_MODE`.
Without it the `APIClient` is never bound to the scanner, so mode requests
have no firmware effect and `async_request_active_window` returns `False`
instead of opening a window — see the _Feature Flag Reference_ section below.

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

| Public surface                                  | Required flag               | Behavior when flag is absent                                                                                                                                                                                                                                                                                     |
| ----------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BleakClient.connect` / GATT operations         | `ACTIVE_CONNECTIONS`        | The scanner is registered as non-connectable. Discovery still works; connect attempts are rejected by `bleak` before reaching this library.                                                                                                                                                                      |
| Decoded vs. raw advertisements                  | `RAW_ADVERTISEMENTS`        | Falls back to `subscribe_bluetooth_le_advertisements` (proxy-side decoded) instead of `subscribe_bluetooth_le_raw_advertisements`. Both paths feed the same scanner.                                                                                                                                             |
| Scanner state / mode + on-demand active windows | `FEATURE_STATE_AND_MODE`    | `subscribe_bluetooth_scanner_state` is skipped and the `APIClient` is not bound to the scanner, so `current_mode` / `requested_mode` stay at their defaults and `habluetooth` cannot open on-demand active-scan windows (`async_request_active_window` returns `False`). Connection-slot tracking is unaffected. |
| `connect(dangerous_use_bleak_cache=…)`          | `REMOTE_CACHING`            | The cached-services hint sent to the proxy is forced off, so the proxy re-discovers services on every connect. `dangerous_use_bleak_cache` still hits the on-host LRU in `_get_services` when populated, and `start_notify` skips the CCCD write because the firmware handles it.                                |
| `BleakClient.pair` / `unpair`                   | `PAIRING`                   | Raises `NotImplementedError("Pairing is not available in this version ESPHome; Upgrade the ESPHome version on the … device.")`.                                                                                                                                                                                  |
| `ESPHomeClient.clear_cache`                     | `CACHE_CLEARING`            | Returns `True` after clearing only the on-host LRU caches; logs `"On device cache clear is not available with this ESPHome version; … Only memory cache will be cleared"`. No proxy round-trip.                                                                                                                  |
| `ESPHomeClient.set_connection_params`           | `CONNECTION_PARAMS_SETTING` | Silently returns after logging `"Setting connection parameters is not available with ESPHome version …; Upgrade the ESPHome version on the device"`. No exception is raised.                                                                                                                                     |

If a method appears to silently do nothing, check the proxy's reported feature
flags first — the warning is logged at WARNING level on the
`bleak_esphome.backend.client` logger.
