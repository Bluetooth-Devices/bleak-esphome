from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypedDict

import habluetooth
from aioesphomeapi import APIClient, ReconnectLogic

import bleak_esphome


class ESPHomeDeviceConfig(TypedDict):
    """Configuration for an ESPHome device."""

    address: str
    noise_psk: str | None


class APIConnectionManager:
    """Manager for the API connection to an ESPHome device."""

    def __init__(self, config: ESPHomeDeviceConfig) -> None:
        """Initialize the API connection manager."""
        self._address = config["address"]
        self._noise_psk = config["noise_psk"]
        self._cli: APIClient = APIClient(
            address=self._address, port=6053, password=None, noise_psk=self._noise_psk
        )
        self._reconnect_logic = ReconnectLogic(
            client=self._cli,
            on_disconnect=self._on_disconnect,
            on_connect=self._on_connect,
        )
        self._unregister_scanner: Callable[[], None] | None = None
        self._start_future: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )

    async def _on_disconnect(self, expected_disconnect: bool) -> None:
        """Handle the disconnection of the API client."""
        if self._unregister_scanner is not None:
            self._unregister_scanner()
            self._unregister_scanner = None

    async def _on_connect(self) -> None:
        """Handle the connection of the API client."""
        device_info = await self._cli.device_info()
        client_data = bleak_esphome.connect_scanner(self._cli, device_info, True)
        scanner = client_data.scanner
        assert scanner is not None  # noqa: S101
        scanner.async_setup()
        self._unregister_scanner = habluetooth.get_manager().async_register_scanner(
            scanner
        )
        if not self._start_future.done():
            self._start_future.set_result(None)

    async def start(self) -> None:
        """Start the API connection."""
        await self._reconnect_logic.start()
        await self._start_future

    async def stop(self) -> None:
        """Stop the API connection."""
        await self._reconnect_logic.stop()
        await self._cli.disconnect()
        if not self._start_future.done():
            self._start_future.cancel()
        if self._unregister_scanner is not None:
            self._unregister_scanner()
            self._unregister_scanner = None
