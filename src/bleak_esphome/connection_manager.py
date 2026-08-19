from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, TypedDict

import habluetooth
from aioesphomeapi import APIClient, ReconnectLogic

import bleak_esphome

from ._cancellation import is_spurious_cancellation

if TYPE_CHECKING:
    from collections.abc import Callable

    from .backend.device import ESPHomeBluetoothDevice

_LOGGER = logging.getLogger(__name__)


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
        self._unsetup_scanner: Callable[[], None] | None = None
        self._disconnect_callbacks: set[Callable[[], None]] | None = None
        self._bluetooth_device: ESPHomeBluetoothDevice | None = None
        self._start_future: asyncio.Future[None] | None = None

    def _teardown_scanner(self) -> None:
        """Unset up and unregister the scanner if wired."""
        unsetup = self._unsetup_scanner
        unregister = self._unregister_scanner
        self._unsetup_scanner = None
        self._unregister_scanner = None
        try:
            if unsetup is not None:
                unsetup()
        finally:
            # The unregister must run even if unsetup raises; skipping it
            # would leak the scanner registration in habluetooth's manager.
            if unregister is not None:
                unregister()

    def _mark_unavailable(self) -> None:
        """
        Close the connector's can_connect gate for this session's proxy.

        Also fails any caller parked waiting for a free connection slot,
        so connect attempts stop burning their timeout on a proxy whose
        API connection is gone.
        """
        if self._bluetooth_device is not None:
            self._bluetooth_device.async_set_unavailable()
            self._bluetooth_device = None

    def _teardown_session(self) -> None:
        """Tear down the per-session client state and the scanner."""
        try:
            # async_set_unavailable never raises by contract; the guard
            # keeps a future regression from skipping the rest anyway.
            self._mark_unavailable()
        finally:
            try:
                if (disconnect_callbacks := self._disconnect_callbacks) is not None:
                    self._disconnect_callbacks = None
                    try:
                        # Each callback discards itself from the set, so
                        # iterate a snapshot to avoid "set changed size
                        # during iteration". A callback ends in consumer
                        # supplied code; one raising must not skip the
                        # other clients.
                        for callback in list(disconnect_callbacks):
                            try:
                                callback()
                            except Exception:  # pylint: disable=broad-except
                                _LOGGER.exception(
                                    "%s: Error in disconnect callback", self._address
                                )
                    finally:
                        # Clear in place: clients hold a reference to this
                        # set object.
                        disconnect_callbacks.clear()
            finally:
                # The scanner unregister must run regardless; skipping it
                # would leak the registration in habluetooth's manager.
                self._teardown_scanner()

    async def _on_disconnect(self, expected_disconnect: bool) -> None:
        """Handle the disconnection of the API client."""
        self._teardown_session()

    async def _on_connect(self) -> None:
        """Handle the connection of the API client."""
        # ``_on_connect`` is only ever invoked by ``ReconnectLogic`` after
        # ``start()`` has constructed ``_cli`` / ``_start_future``.
        assert self._cli is not None  # noqa: S101
        device_info = await self._cli.device_info()
        client_data = bleak_esphome.connect_scanner(self._cli, device_info, True)
        scanner = client_data.scanner
        assert scanner is not None  # noqa: S101
        self._unsetup_scanner = scanner.async_setup()
        self._unregister_scanner = habluetooth.get_manager().async_register_scanner(
            scanner
        )
        self._disconnect_callbacks = client_data.disconnect_callbacks
        self._bluetooth_device = client_data.bluetooth_device
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

        Call once per manager instance; a second call raises ``RuntimeError``
        to prevent leaking the prior ``APIClient`` / ``ReconnectLogic`` (and
        its background reconnect task) by overwriting them.

        Raises:
            ESPHomeStartAborted: if ``stop()`` is called before the first
                successful connect.
            RuntimeError: if ``start()`` has already been called.

        """
        if self._reconnect_logic is not None:
            raise RuntimeError(
                "APIConnectionManager.start() has already been called; "
                "create a new manager instance to reconnect."
            )
        self._cli = APIClient(
            address=self._address,
            port=6053,
            password=None,
            noise_psk=self._noise_psk,
        )
        self._reconnect_logic = ReconnectLogic(
            client=self._cli,
            on_disconnect=self._on_disconnect,
            on_connect=self._on_connect,
        )
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
        # Close the connect gate first so no new connection attempts are
        # offered this proxy while its API connection is being torn down.
        self._mark_unavailable()
        try:
            if self._reconnect_logic is not None:
                await self._reconnect_logic.stop()
        except Exception:
            # A later shutdown step can replace this as the propagating
            # error; log so the root cause is never lost. Cancellation
            # passes through unlogged.
            _LOGGER.exception("%s: Error stopping reconnect logic", self._address)
            raise
        finally:
            # Each shutdown step runs even if the previous one raised;
            # otherwise a failing reconnect stop would leave the API
            # client connected and a pending start() blocked forever.
            try:
                if self._cli is not None:
                    await self._cli.disconnect()
            except Exception:
                _LOGGER.exception("%s: Error disconnecting API client", self._address)
                raise
            finally:
                if self._start_future is not None and not self._start_future.done():
                    self._start_future.cancel()
                # Same teardown as _on_disconnect so a stop() that never
                # saw a disconnect callback still clears the session state.
                self._teardown_session()
