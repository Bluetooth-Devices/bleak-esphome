"""
Low-level example: wire ``connect_scanner`` to a single ESPHome proxy.

``APIConnectionManager`` (see ``setup_scanner.py``) is the recommended entry
point — it owns the ``APIClient``, drives ``ReconnectLogic``, registers the
scanner, and tears everything down for you. Reach for ``connect_scanner``
only when you already manage the ``APIClient`` lifecycle yourself.

``connect_scanner`` leaves three jobs to the caller, all of which this
example performs explicitly:

1. Call ``client_data.scanner.async_setup()`` to attach the scanner to the
   running loop.
2. Register the scanner with the host-side Bluetooth manager (and
   un-register it when the ESP disconnects).
3. Fire every callback in ``client_data.disconnect_callbacks`` when the ESP
   disconnects. Iterate a snapshot of the set — each callback removes
   itself during cleanup.

Replace ``DEVICE_ADDRESS`` / ``NOISE_PSK`` with your proxy's details before
running. This talks to real hardware, so it cannot run in CI.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import bleak
import habluetooth
from aioesphomeapi import APIClient
from habluetooth import BluetoothScanningMode

import bleak_esphome

if TYPE_CHECKING:
    from habluetooth.const import CALLBACK_TYPE

    from bleak_esphome.backend.client import ESPHomeClientData

_LOGGER = logging.getLogger(__name__)

DEVICE_ADDRESS = "XXXX.local."
NOISE_PSK: str | None = None
SCAN_SECONDS = 10


async def run() -> None:
    """Connect one proxy, scan for ``SCAN_SECONDS``, then tear it all down."""
    # The host-side manager must exist before a scanner is registered.
    await habluetooth.BluetoothManager().async_setup()

    cli = APIClient(
        address=DEVICE_ADDRESS,
        port=6053,
        password=None,
        noise_psk=NOISE_PSK,
    )

    # Wrap the whole setup+scan sequence so teardown runs even if connect(),
    # device_info(), connect_scanner(), or registration raises. Each cleanup
    # step is guarded so only successfully initialized resources are released.
    client_data: ESPHomeClientData | None = None
    unregister_scanner: CALLBACK_TYPE | None = None
    try:
        await cli.connect(login=True)
        device_info = await cli.device_info()

        # connect_scanner subscribes to the proxy's advertisement,
        # scanner-state, and connection-slot streams and hands back the wiring.
        client_data = bleak_esphome.connect_scanner(cli, device_info, available=True)
        scanner = client_data.scanner
        if scanner is None:  # pragma: no cover - defensive; always set on success
            raise RuntimeError("connect_scanner did not return a scanner")

        # Responsibility 1: attach the scanner to the running loop.
        scanner.async_setup()
        # Responsibility 2: register the scanner with the host-side manager.
        unregister_scanner = habluetooth.get_manager().async_register_scanner(scanner)

        # Pin a scanning mode explicitly. AUTO maps to PASSIVE on the proxy and
        # opens brief ACTIVE windows on demand. This is a no-op against the
        # firmware if the proxy lacks FEATURE_STATE_AND_MODE; the intent is
        # still recorded locally.
        scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)

        # Use bleak normally — discovery is fed by the proxy's advertisements.
        # The discovery window is exactly SCAN_SECONDS.
        devices = await bleak.BleakScanner.discover(
            timeout=SCAN_SECONDS, return_adv=True
        )
        for device, adv in devices.values():
            print(f"{device} (rssi={adv.rssi})")
    finally:
        # Responsibility 3: fire the disconnect callbacks (snapshot the set —
        # each callback removes itself). Guard each one so a single bad
        # callback cannot abort the rest of teardown, and keep un-register and
        # disconnect in their own guarded steps so they always run.
        if client_data is not None:
            for callback in list(client_data.disconnect_callbacks):
                try:
                    callback()
                except Exception:
                    _LOGGER.exception("disconnect callback failed")
        if unregister_scanner is not None:
            try:
                unregister_scanner()
            except Exception:
                _LOGGER.exception("scanner un-registration failed")
        await cli.disconnect()


logging.basicConfig(level=logging.DEBUG)
asyncio.run(run())
