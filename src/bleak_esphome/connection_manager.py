from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypedDict

import habluetooth
from aioesphomeapi import APIClient, ReconnectLogic

import bleak_esphome

from ._cancellation import is_spurious_cancellation

if TYPE_CHECKING:
    from collections.abc import Callable


class ESPHomeStartAborted(Exception):
    """Raised when ``APIConnectionManager.start()`` is aborted by ``stop()``."""


class ESPHomeDeviceConfig(TypedDict):
    """Configuration for an ESPHome device."""

    address: str
    noise_psk: str | None


class APIConnectionManager:
    """Manager for the API connection to an ESPHome device."""

    def __init__(self, config: ESPHomeDeviceConfig) -> None:
        """
        Initialize the API connection manager.

        Construction is side-effect-free and does not require a running event
        loop. The ``APIClient`` / ``ReconnectLogic`` instances and the start
        future are created in :meth:`start` so the manager can be constructed
        synchronously outside an async context.
        """
        self._address = config["address"]
        self._noise_psk = config["noise_psk"]
        self._cli: APIClient | None = None
        self._reconnect_logic: ReconnectLogic | None = None
        self._unregister_scanner: Callable[[], None] | None = None
        self._disconnect_callbacks: set[Callable[[], None]] | None = None
        self._start_future: asyncio.Future[None] | None = None

    async def _on_disconnect(self, expected_disconnect: bool) -> None:
        """Handle the disconnection of the API client."""
        if self._disconnect_callbacks is not None:
            # Each callback discards itself from the set, so iterate a
            # snapshot to avoid "set changed size during iteration".
            for callback in list(self._disconnect_callbacks):
                callback()
            self._disconnect_callbacks = None
        if self._unregister_scanner is not None:
            self._unregister_scanner()
            self._unregister_scanner = None

    async def _on_connect(self) -> None:
        """Handle the connection of the API client."""
        # ``_on_connect`` is only ever invoked by ``ReconnectLogic`` after
        # ``start()`` has constructed ``_cli`` / ``_start_future``.
        assert self._cli is not None  # noqa: S101
        device_info = await self._cli.device_info()
        client_data = bleak_esphome.connect_scanner(self._cli, device_info, True)
        scanner = client_data.scanner
        assert scanner is not None  # noqa: S101
        scanner.async_setup()
        self._unregister_scanner = habluetooth.get_manager().async_register_scanner(
            scanner
        )
        self._disconnect_callbacks = client_data.disconnect_callbacks
        if self._start_future is not None and not self._start_future.done():
            self._start_future.set_result(None)

    async def start(self) -> None:
        """
        Start the API connection and wait for the first successful connect.

        Constructs the ``APIClient`` and ``ReconnectLogic`` on first call so
        no event loop work happens at ``__init__`` time. Returns once
        ``_on_connect`` has fired (scanner registered, ``disconnect_callbacks``
        captured). If ``stop()`` is called before the first connect completes,
        the awaiting task is unblocked with ``ESPHomeStartAborted`` rather than
        a bare ``CancelledError`` so it does not surface as a spurious
        cancellation in ``TaskGroup`` or ``asyncio.timeout`` contexts.

        Raises:
            ESPHomeStartAborted: if ``stop()`` is called before the first
                successful connect.

        """
        if self._cli is None:
            self._cli = APIClient(
                address=self._address,
                port=6053,
                password=None,
                noise_psk=self._noise_psk,
            )
        if self._reconnect_logic is None:
            self._reconnect_logic = ReconnectLogic(
                client=self._cli,
                on_disconnect=self._on_disconnect,
                on_connect=self._on_connect,
            )
        if self._start_future is None:
            self._start_future = asyncio.get_running_loop().create_future()

        await self._reconnect_logic.start()
        try:
            await self._start_future
        except asyncio.CancelledError:
            # If the awaiting task is not actually being cancelled, the
            # CancelledError came from ``stop()`` cancelling the
            # ``_start_future`` directly. Convert it to ``ESPHomeStartAborted``
            # so it does not leak as a spurious cancellation that breaks
            # ``TaskGroup`` / ``asyncio.timeout`` semantics for callers.
            if is_spurious_cancellation():
                raise ESPHomeStartAborted("API connection start was aborted") from None
            raise

    async def stop(self) -> None:
        """Stop the API connection."""
        if self._reconnect_logic is not None:
            await self._reconnect_logic.stop()
        if self._cli is not None:
            await self._cli.disconnect()
        if self._start_future is not None and not self._start_future.done():
            self._start_future.cancel()
        if self._unregister_scanner is not None:
            self._unregister_scanner()
            self._unregister_scanner = None
