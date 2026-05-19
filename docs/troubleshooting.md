(troubleshooting)=

# Troubleshooting

This page collects the symptoms most often reported against `bleak-esphome` and
maps each one to the actual cause. The library degrades gracefully when the
proxy firmware is missing a feature flag, which means problems usually appear
as _silent fallbacks_ or generic `BleakError`s rather than typed exceptions —
so the first step is almost always "check the proxy's reported feature flags".

## Inspecting the proxy's feature flags

Every diagnostic below ultimately comes back to the bitmask returned by
`DeviceInfo.bluetooth_proxy_feature_flags_compat(api_version)`. To inspect it
from your own code, take the `APIConnectionManager` you constructed and read
the value after the first successful connection:

```python
from aioesphomeapi import BluetoothProxyFeature

flags = device_info.bluetooth_proxy_feature_flags_compat(cli.api_version)
for flag in BluetoothProxyFeature:
    print(f"{flag.name}: {bool(flags & flag.value)}")
```

If you cannot run code against the proxy, raise the log level to `DEBUG` on
the `bleak_esphome.connect` logger — `connect_scanner()` logs the negotiated
`feature_flags` and `connectable` values on every connection.

```python
import logging

logging.getLogger("bleak_esphome").setLevel(logging.DEBUG)
```

## `clear_cache()` returns `True` but the proxy never re-discovers services

The `CACHE_CLEARING` flag is missing on the proxy firmware. `clear_cache()`
still clears the on-host LRU caches (the local GATT service map and the
cached MTU) and returns `True`, but it does not perform a proxy-side round
trip. Look for this WARNING on the `bleak_esphome.backend.client` logger:

```
On device cache clear is not available with this ESPHome version;
Upgrade the ESPHome version on the device <name>;
Only memory cache will be cleared
```

The fix is to upgrade the ESPHome firmware on the proxy node. The host-side
cache eviction is enough for many "characteristics moved after a firmware
update" scenarios, but it cannot recover from a stale cache on the proxy
itself.

## `set_connection_params()` silently does nothing

The `CONNECTION_PARAMS_SETTING` flag is missing. Unlike most other extension
methods, `set_connection_params()` returns without raising — the call appears
to succeed but no GAP update request is sent. Look for:

```
Setting connection parameters is not available with ESPHome version <ver>
on device <name>; Upgrade the ESPHome version on the device
```

Upgrade the proxy firmware. The flag was added relatively late, so older
proxies that otherwise work fine for connect/read/write/notify will not
support interval tuning.

## `BleakClient.pair()` / `unpair()` raises `NotImplementedError`

The `PAIRING` flag is missing. `bleak-esphome` raises immediately rather than
attempting a proxy call that the firmware cannot service:

```python
NotImplementedError(
    "Pairing is not available in this version ESPHome; "
    "Upgrade the ESPHome version on the <name> device."
)
```

This is a hard error — there is no host-side fallback. Either upgrade the
proxy firmware or avoid `pair()` / `unpair()` for that device.

## `BleakError("Failed to get services from remote esp")`

The proxy returned a `BluetoothGATTServices` response with an empty
`services` list. This usually means GATT discovery on the peripheral itself
failed (the peripheral disconnected mid-discovery, or its GATT database is
not yet ready). It is _not_ a host-side cache problem.

Retry the connection. If the failure is reproducible against the same
peripheral, the bug is on the peripheral or the proxy — not in
`bleak-esphome`. The local service cache is short-circuited only when
`REMOTE_CACHING` is set _and_ the proxy reports a non-empty service list, so
clearing it does not help here.

## Connect attempts are rejected by `bleak` before the proxy is ever called

The scanner is registered as non-connectable. This happens when the
`ACTIVE_CONNECTIONS` flag is missing — the proxy is a passive listener and
forwards advertisements only. Discovery still works; connections do not.

To confirm, check the DEBUG log line from `connect_scanner`:

```
<name> [<source>]: Connecting scanner feature_flags=<bitmask>, connectable=False
```

If `connectable=False`, the proxy firmware does not support active
connections. Flash a firmware build that includes
`bluetooth_proxy:` with `active: true`.

## Discovery sees no advertisements

Symptoms: `BleakScanner.discover()` returns nothing, even though the proxy
itself sees advertisements in its own logs. Check, in order:

1. The proxy actually connected. `APIConnectionManager.start()` blocks until
   the first successful API connection — if it raises
   `ESPHomeStartAborted`, the manager was stopped before the first connect.
2. The scanner was registered with `habluetooth`. When you use
   `APIConnectionManager`, this happens automatically in `_on_connect`. When
   you call `connect_scanner()` directly, you must call
   `client_data.scanner.async_setup()` _and_ register the scanner with
   `habluetooth.get_manager().async_register_scanner(...)` yourself — see
   {ref}`usage`.
3. The `RAW_ADVERTISEMENTS` branch matches the firmware. The library picks
   between `subscribe_bluetooth_le_raw_advertisements` and
   `subscribe_bluetooth_le_advertisements` based on the flag; both paths
   feed the same scanner, so if one is silent the issue is at the proxy.

## `ESPHomeStartAborted` vs `asyncio.CancelledError`

If `APIConnectionManager.start()` is in flight when you call `stop()`,
`start()` raises `ESPHomeStartAborted` rather than letting a bare
`CancelledError` propagate. This preserves `TaskGroup` and
`asyncio.timeout()` semantics — the typed exception means "we asked it to
stop", not "the surrounding task was cancelled". See
{ref}`usage`'s "Handling start cancellation" section for the catch pattern.

If you _do_ see `CancelledError` from `start()`, your awaiting task was
cancelled from somewhere else — `bleak-esphome` re-raises in that case so
the cancellation propagates correctly.
