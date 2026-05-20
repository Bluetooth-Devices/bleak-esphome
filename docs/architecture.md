(architecture)=

# Architecture

This page explains what `bleak-esphome` does, where the ESPHome Bluetooth Proxy is
implemented, and how the pieces fit together. If you only want to use the library,
see {ref}`usage`.

## What this library is — and what it is not

`bleak-esphome` is the glue layer that lets a Python application talk to remote
Bluetooth Low Energy (BLE) peripherals **through an ESP32 running ESPHome with the
Bluetooth Proxy component enabled**. It does **not** implement the Bluetooth Proxy
itself. The proxy is firmware that runs on the ESP32; this library is the host-side
client that consumes the proxy's API.

The split is:

| Layer                                                   | Where it lives               | Repository                                                                                        |
| ------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------- |
| ESP32 firmware (Bluetooth Proxy component)              | On the ESP32, written in C++ | [esphome/esphome](https://github.com/esphome/esphome) — see `esphome/components/bluetooth_proxy/` |
| Native ESPHome API (protobuf over TCP, port 6053)       | On the ESP32                 | [esphome/esphome](https://github.com/esphome/esphome) — see `esphome/components/api/`             |
| Python client for the ESPHome API                       | Host (your app)              | [esphome/aioesphomeapi](https://github.com/esphome/aioesphomeapi)                                 |
| `bleak`-compatible adapter on top of `aioesphomeapi`    | Host (your app)              | **this repo**                                                                                     |
| Remote-scanner / connection-slot bookkeeping primitives | Host (your app)              | [Bluetooth-Devices/habluetooth](https://github.com/Bluetooth-Devices/habluetooth)                 |
| Standard BLE client API consumed by user code           | Host (your app)              | [hbldh/bleak](https://github.com/hbldh/bleak)                                                     |

So when you call `bleak.BleakScanner.discover(...)` in an app that has set up an
`APIConnectionManager`, what really happens is:

1. The ESP32 scans for BLE advertisements over the air.
2. The Bluetooth Proxy component forwards advertisements to your host over Wi-Fi via
   the ESPHome native API.
3. `aioesphomeapi` decodes the protobuf messages.
4. `bleak-esphome`'s `ESPHomeScanner` translates each advertisement into the shape
   that `habluetooth` and `bleak` expect.
5. `bleak`'s discovery code sees those advertisements as if they had been seen by a
   local adapter.

Active connections (GATT reads, writes, notifications) work the same way in reverse:
`bleak`'s `BleakClient` talks to an `ESPHomeClient` (in `backend/client.py`), which
sends connect / read / write requests to the ESP32, which performs the actual BLE
operation against the peripheral.

## Where the proxy is implemented

Short answer: **not here.** The Bluetooth Proxy is implemented in the
[ESPHome](https://github.com/esphome/esphome) firmware project, in
`esphome/components/bluetooth_proxy/`. The API messages it exchanges with hosts are
defined in `esphome/components/api/api.proto`.

You enable the proxy by adding the `bluetooth_proxy:` component to your ESPHome YAML
configuration and flashing it to an ESP32. ESPHome publishes ready-made proxy
firmwares at <https://esphome.io/projects/?type=bluetooth>.

What this repository contains:

- `src/bleak_esphome/connection_manager.py` — `APIConnectionManager`, the convenience
  wrapper that opens the ESPHome API connection, performs `ReconnectLogic`, and
  registers a scanner with `habluetooth`.
- `src/bleak_esphome/connect.py` — `connect_scanner()`, which wires up an
  `aioesphomeapi.APIClient` to an `ESPHomeScanner` and `ESPHomeClient` and subscribes
  to advertisement / scanner-state / connection-slot streams.
- `src/bleak_esphome/backend/scanner.py` — `ESPHomeScanner`, a remote scanner that
  feeds advertisements received from the ESP32 into `habluetooth`.
- `src/bleak_esphome/backend/client.py` — `ESPHomeClient`, the `BleakClient`-shaped
  backend that performs GATT operations through the ESP32.
- `src/bleak_esphome/backend/device.py` — `ESPHomeBluetoothDevice`, bookkeeping for
  per-ESP32 state (availability, free connection slots, allocations).
- `src/bleak_esphome/backend/cache.py` — local GATT service cache.

## How features are negotiated

When the ESPHome API connection comes up, `connect_scanner()` reads
`DeviceInfo.bluetooth_proxy_feature_flags_compat(api_version)` from `aioesphomeapi`.
That bitmask drives every subsequent decision:

- `ACTIVE_CONNECTIONS` — whether the proxy can open BLE connections, or only forward
  advertisements (passive listener). If unset, the scanner is registered as
  non-connectable.
- `RAW_ADVERTISEMENTS` — if set, the host subscribes to raw advertisement frames; if
  not, it falls back to per-advertisement decoded messages.
- `FEATURE_STATE_AND_MODE` — if set, the host subscribes to scanner state updates and
  tracks both the current scanner state (`IDLE` / `STARTING` / `RUNNING` / `STOPPING`
  / `STOPPED` / `FAILED`) and the active scanning mode (`PASSIVE` / `ACTIVE`).
- `REMOTE_CACHING` — gates the cached-services hint sent on connect. When unset the
  hint is forced off, so the proxy re-discovers services on every connect; the
  on-host LRU cache still works.
- `PAIRING` — required for `BleakClient.pair` and `unpair`. If unset, those calls
  raise `NotImplementedError` rather than silently no-oping.
- `CACHE_CLEARING` — required for {ref}`usage`'s `clear_cache()` extension.
- `CONNECTION_PARAMS_SETTING` — required for `set_connection_params()`.

The proxy-side `BluetoothProxyFeature` enum also defines `PASSIVE_SCAN`, but no
host-side code path in this library currently checks it — passive scanning is
inferred from the absence of `ACTIVE_CONNECTIONS` rather than from a dedicated
flag. See the {ref}`usage` "Feature Flag Reference" table for what callers see
when each flag is missing.

Older proxy firmwares simply lack these flags; the library degrades gracefully (it
logs a warning and skips the unsupported call) rather than refusing to start.

## Who can use it

The library has no Home Assistant dependency. It is plain Python, built on
`asyncio`, and works in any host environment that can reach the ESP32 over TCP and
that can run `bleak` and `habluetooth`. Concretely:

- **Home Assistant** uses it under the hood for its ESPHome Bluetooth integration —
  but it is not the only consumer.
- **Stand-alone Python applications** can use it; see {ref}`usage` for a minimal
  example that does not import anything from Home Assistant.
- **Home Assistant add-ons** that run Python can use it the same way a stand-alone
  app does. There is no special add-on hook; the only requirement is that the
  add-on can open a TCP connection to the ESP32 on port 6053.

If you are evaluating whether to consume the ESPHome Bluetooth Proxy from an
unrelated application, the practical entry point is `APIConnectionManager` plus a
list of `ESPHomeDeviceConfig` entries, as shown in {ref}`usage`.

## See also

- ESPHome Bluetooth Proxy component:
  <https://esphome.io/components/bluetooth_proxy.html>
- Pre-built proxy firmwares: <https://esphome.io/projects/?type=bluetooth>
- `aioesphomeapi` (the protobuf client this library sits on top of):
  <https://github.com/esphome/aioesphomeapi>
- `habluetooth` (remote-scanner primitives):
  <https://github.com/Bluetooth-Devices/habluetooth>
