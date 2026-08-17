(troubleshooting)=

# Troubleshooting

This page collects the symptoms most often reported against `bleak-esphome`
and maps each one to the actual cause. The library degrades gracefully when
the proxy firmware is missing a feature flag, which means problems usually
appear as _silent fallbacks_ or generic `BleakError`s rather than typed
exceptions — so the first step is almost always "check the proxy's reported
feature flags".

## Inspecting the proxy's feature flags

Every diagnostic below ultimately comes back to the bitmask returned by
`DeviceInfo.bluetooth_proxy_feature_flags_compat(api_version)`. To inspect it
from your own code, take the `DeviceInfo` you fetched and the connected
client's `api_version` and read the value:

```python
from aioesphomeapi import BluetoothProxyFeature

# device_info: the DeviceInfo you fetched; cli: the connected APIClient
flags = device_info.bluetooth_proxy_feature_flags_compat(cli.api_version)
for flag in BluetoothProxyFeature:
    print(f"{flag.name}: {bool(flags & flag.value)}")
```

If you cannot run code against the proxy, raise the log level to `DEBUG` on
the `bleak_esphome` logger — `connect_scanner()` logs the negotiated
`feature_flags` and `connectable` values on every connection:

```python
import logging

logging.getLogger("bleak_esphome").setLevel(logging.DEBUG)
```

```
<name> [<source>]: Connecting scanner feature_flags=<bitmask>, connectable=<bool>
```

## `clear_cache()` returns `True` but the proxy never re-discovers services

The `CACHE_CLEARING` flag is missing on the proxy firmware. `clear_cache()`
still clears the on-host caches (the local GATT service map and the cached
MTU) and returns `True`, but it does not perform a proxy-side round trip.
Look for this WARNING on the `bleak_esphome.backend.client` logger:

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
to succeed but no connection-parameter update request is sent. Look for:

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

The proxy returned a GATT services response with an empty `services` list.
This usually means GATT discovery on the peripheral itself failed (the
peripheral disconnected mid-discovery, or its GATT database is not yet
ready). It is _not_ a host-side cache problem.

Retry the connection. If the failure is reproducible against the same
peripheral, the bug is on the peripheral or the proxy — not in
`bleak-esphome`. The local service cache is consulted only when
`REMOTE_CACHING` (or `dangerous_use_bleak_cache`) is set _and_ a cached
collection exists, so clearing it does not help here.

## Connections drop repeatedly with `reason 0x100` or `0x3e`

Symptoms: a device connects, then the proxy log shows a repeating
connect/disconnect cycle, often with two numeric reasons:

```
[ESP_GATTC_DISCONNECT_EVT, reason 0x100]
[Connecting v3 without cache]
[hcif disc complete: rsn 0x3e]   (repeats several times)
```

These numbers are **ESP-IDF GATT connection-reason codes**
(`esp_gatt_conn_reason_t`), reported by the proxy firmware and forwarded
through `aioesphomeapi`. They are _not_ Bluetooth HCI error codes, and
`bleak-esphome` neither generates nor interprets them — it only surfaces the
disconnect. The two most common:

- `0x100` — `ESP_GATT_CONN_CONN_CANCEL`: the connection was cancelled
  **locally**, not terminated by the remote device. In a multi-proxy setup
  this typically means the connection was withdrawn or reassigned to another
  proxy (see the next section), _not_ that the peripheral hung up.
- `0x3e` — `ESP_GATT_CONN_FAIL_ESTABLISH`: the link-layer connection could
  not be established inside the supervision window — usually 2.4 GHz RF
  contention, or the peripheral not emitting a connectable advertisement in
  time.

Because both originate in the proxy/peripheral radio link, they are addressed
at that layer rather than in this library: reduce Wi-Fi/BLE contention on the
proxy's channel, improve RF line-of-sight to the peripheral, or reduce how
many devices a single proxy is asked to hold at once.

## `Proxy became unavailable while waiting for a free BLE connection slot`

A connect attempt was waiting for a free connection slot on a proxy whose
API connection dropped. Instead of parking for the full timeout on a proxy
that is provably gone, the waiter fails immediately with this message so
the retry logic can move to another proxy. The fail fast disarms as soon
as the proxy reports slot state again, or when a caller reusing the
device marks it available on reconnect.

## `The proxy has not answered the last N connect requests`

Symptoms: every connect attempt to one device fails after the full connect
timeout, and this library logs

```
The proxy has not answered the last 5 connect requests; it accepted each one
but never reported the connection state, so this device cannot be reached
through this proxy.
```

Meanwhile the proxy's own log shows the link being established normally:

```
[bluetooth_proxy] [0] [AA:BB:CC:DD:EE:FF] Connecting v3 without cache
[esp32_ble_client] [0] [AA:BB:CC:DD:EE:FF] Connection open
[esp32_ble_client] [0] [AA:BB:CC:DD:EE:FF] Service discovery complete
```

The GATT connection succeeded; what never arrives is the
`BluetoothDeviceConnectionResponse` that tells the host about it. Because the
host is still waiting, it tears the connection down when the timeout expires,
and the cycle repeats.

This does not recover on its own. The uncached connect
(`CONNECT_V3_WITHOUT_CACHE`) is the only way to populate the service cache —
the proxy discards its service list after sending it — so a connect that never
completes can never produce a cache, and every later attempt takes the same
uncached path. Restarting the proxy is a workaround; the fix is on the proxy.

Upgrade the proxy firmware. One known instance is an ESPHome bug on the
uncached connect path, where the connected reply was only sent once _both_ the
MTU and service-discovery events had arrived — so a peripheral that never
completes the MTU exchange left the reply unsent. It affects ESPHome through
2026.7.x and is fixed in 2026.8.0 (esphome/esphome#18198).

If the warning persists on current firmware, capture the proxy log for one
attempt and open an issue with both sides of the exchange.

## Can I pin a BLE device to a specific proxy?

No. `bleak-esphome` does not decide which proxy connects to which device. It
reports each proxy's connection-slot allocations upward (via
`ESPHomeBluetoothDevice.async_subscribe_connection_slots`) and provides the
scanner/client backend; the choice of _which_ proxy services a given device
is made by `habluetooth`'s connection manager from the observed RSSI and the
free slots on each proxy. When two proxies both hear the same devices,
habluetooth may move a device between them — which surfaces as the `0x100`
local-cancel disconnect above.

There is no device→proxy affinity API in this library. To bias placement,
influence the inputs habluetooth uses rather than looking for a knob here:
give each proxy a clearly stronger signal for its intended device (position
and antenna orientation), and avoid having two proxies with near-identical
RSSI competing for the same peripheral.

## When does `disconnected_callback` fire?

Whenever the proxy reports the link down for a connection that had come
up, including a drop while pairing or service discovery is still
running, matching bleak's bluez backend for device initiated drops; the
callback persists across connect and disconnect cycles on a reused
client. A `disconnect()` you requested also fires it, and so does the
reconciliation teardown described below. Unlike bluez, library side
abandonment of a failed attempt is silent, because the consumer never
received the client; it surfaces through the raising `connect()` alone.
If the link drops during setup but the
discovery response still resolves, `connect()` raises
`BleakError("<device>: Disconnected during connect setup")` rather than
returning a client on a dead link.

## My `disconnected_callback` fired without a disconnect event in the logs

A connected client can be torn down by allocation reconciliation, without a
`connected=false` notification ever arriving. Every connection-slot update
from the proxy carries the authoritative list of allocated (connected)
addresses; if a client this library believes is connected is missing from
that list, the proxy no longer holds the connection — its `connected=false`
notification was lost (a congested link, or an ESP-side link loss that
never produced one) — and the
client is disconnected locally so the consumer can reconnect instead of
holding a phantom connection forever. Because it means the proxy and the
host were out of sync, this path logs a WARNING:

```
<name> [<mac>]: Reconciling stale connection to <address>: not in allocated list [...]
```

The list is only trusted when its length matches the used slot count
(`limit - free`). Firmware maintains the two as one fact, an address enters
the list when its slot is reserved, before the link is even attempted, so
they always match when the list is reported at all. Firmware that predates
the allocated list reports used slots with an empty list; that mismatch
skips reconciliation, so it cannot tear down a healthy client.

## `Failed to release ESP-side connection` warnings

When a connect attempt is abandoned after the proxy already reported the
link up (a cancellation, an error after link up, a failed pairing or
service discovery), the library sends a fire and forget disconnect so the
proxy's connection slot is freed. If that send fails for a reason other
than the API connection being gone, this warning names the device:

```
<name> [<source>]: <device>: Failed to release ESP-side connection, the proxy slot may stay allocated until it disconnects on its own: ...
```

The slot recovers when the proxy notices the dead link on its own or when
its API connection drops, but until then it counts against the proxy's
limit. A dead API connection is logged at DEBUG instead, because the
firmware tears down every link it holds once its subscriber is gone —
nothing leaks in that case.

## Connect attempts are rejected by `bleak` before the proxy is ever called

The scanner is registered as non-connectable. This happens when the
`ACTIVE_CONNECTIONS` flag is missing — the proxy is a passive listener and
forwards advertisements only. Discovery still works; connections do not.

To confirm, check the DEBUG log line from `connect_scanner`:

```
<name> [<source>]: Connecting scanner feature_flags=<bitmask>, connectable=False
```

If `connectable=False`, the proxy firmware does not support active
connections. Flash a firmware build whose `bluetooth_proxy:` block sets
`active: true`.

## Discovery sees no advertisements

Symptoms: discovery returns nothing, even though the proxy itself sees
advertisements in its own logs. Check, in order:

1. The proxy actually connected. `APIConnectionManager.start()` blocks until
   the first successful API connection — if it raises `ESPHomeStartAborted`,
   the manager was stopped before the first connect.
2. The scanner was registered with `habluetooth`. When you use
   `APIConnectionManager`, this happens automatically on connect. When you
   call `connect_scanner()` directly, you must call
   `client_data.scanner.async_setup()` _and_ register the scanner with
   `habluetooth.get_manager().async_register_scanner(...)` yourself — see
   {ref}`usage`.
3. The advertisement subscription matches the firmware. The library picks
   between `subscribe_bluetooth_le_raw_advertisements` and
   `subscribe_bluetooth_le_advertisements` based on the
   `RAW_ADVERTISEMENTS` flag; both paths feed the same scanner, so if one is
   silent the issue is at the proxy.

## `ESPHomeStartAborted` vs `asyncio.CancelledError`

If `APIConnectionManager.start()` is in flight when you call `stop()`,
`start()` raises `ESPHomeStartAborted` rather than letting a bare
`CancelledError` propagate. This preserves `TaskGroup` and
`asyncio.timeout()` semantics — the typed exception means "we asked it to
stop", not "the surrounding task was cancelled". See the _Handling start
cancellation_ section in {ref}`usage` for the catch pattern.

If you _do_ see `CancelledError` from `start()`, your awaiting task was
cancelled from somewhere else — `bleak-esphome` re-raises in that case so
the cancellation propagates correctly.
