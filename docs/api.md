# API reference

Auto-generated reference for the public surface of `bleak_esphome` — the four
names exported from the top-level package. For how these pieces fit together,
see [the architecture overview](architecture.md); for task-oriented examples,
see [usage](usage.md).

Everything documented here is re-exported from `bleak_esphome` directly, so the
import you write in application code is, for example:

```python
from bleak_esphome import APIConnectionManager, ESPHomeDeviceConfig
```

## High-level entry point

`APIConnectionManager` is the standalone, Home-Assistant-free way to drive a
Bluetooth proxy: hand it a device config, `await start()`, and it owns the
`APIClient`, reconnect logic, and scanner registration for you.

```{eval-rst}
.. autoclass:: bleak_esphome.APIConnectionManager
   :members:
   :undoc-members:

.. autoclass:: bleak_esphome.ESPHomeDeviceConfig
   :members:
   :undoc-members:

.. autoexception:: bleak_esphome.ESPHomeStartAborted
```

## Low-level escape hatch

`connect_scanner` is for advanced callers that manage their own `APIClient`
lifecycle. It wires an `aioesphomeapi.APIClient` to an `ESPHomeScanner` +
`ESPHomeClient` and returns the assembled `ESPHomeClientData`, but leaves the
three caller responsibilities (scanner setup, disconnect callbacks, manager
registration) up to you — read the docstring carefully before reaching for it.

```{eval-rst}
.. autofunction:: bleak_esphome.connect_scanner
```
