"""Tests for ``bleak_esphome.connection_manager``."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from bleak_esphome.connection_manager import (
    APIConnectionManager,
    ESPHomeDeviceConfig,
    ESPHomeStartAborted,
)


@pytest.mark.asyncio
async def test_start_aborted_by_stop_raises_start_aborted() -> None:
    """
    ``start()`` raises ``ESPHomeStartAborted`` when ``stop()`` cancels its future.

    The ``_start_future`` is a local future that ``stop()`` cancels to
    abort a pending ``start()``. The resulting ``CancelledError`` must
    be converted to ``ESPHomeStartAborted`` so it does not leak as a spurious
    cancellation that breaks ``TaskGroup`` / ``asyncio.timeout``
    semantics in callers (whose task is not actually being cancelled).
    """
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch(
        "bleak_esphome.connection_manager.ReconnectLogic"
    ) as mock_reconnect_logic_cls:
        mock_reconnect_logic = mock_reconnect_logic_cls.return_value
        mock_reconnect_logic.start = AsyncMock()
        mock_reconnect_logic.stop = AsyncMock()
        manager = APIConnectionManager(config)
        with patch.object(manager._cli, "disconnect", AsyncMock()):
            start_task = asyncio.create_task(manager.start())
            # Yield so start() reaches ``await self._start_future``.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            await manager.stop()
            with pytest.raises(ESPHomeStartAborted):
                await start_task
            assert start_task.cancelling() == 0
            assert not start_task.cancelled()


@pytest.mark.asyncio
async def test_start_real_task_cancel_propagates_cancelled_error() -> None:
    """
    Genuine task cancellation of ``start()`` propagates ``CancelledError``.

    When the awaiting task is genuinely cancelled (e.g. by a parent
    ``TaskGroup`` or ``asyncio.timeout``), the ``CancelledError`` must
    propagate so structured concurrency primitives can observe it.
    """
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch(
        "bleak_esphome.connection_manager.ReconnectLogic"
    ) as mock_reconnect_logic_cls:
        mock_reconnect_logic = mock_reconnect_logic_cls.return_value
        mock_reconnect_logic.start = AsyncMock()
        manager = APIConnectionManager(config)
        start_task = asyncio.create_task(manager.start())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert start_task.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await start_task
        assert start_task.cancelled()


@pytest.mark.asyncio
async def test_on_connect_registers_scanner_and_resolves_start() -> None:
    """``_on_connect`` wires the scanner and unblocks a pending ``start()``.

    The reconnect callback fetches device info, builds a scanner via
    ``bleak_esphome.connect_scanner``, sets it up, registers it with the
    habluetooth manager, and resolves ``_start_future`` so a waiting
    ``start()`` returns.
    """
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    mock_scanner = Mock()
    mock_client_data = Mock()
    mock_client_data.scanner = mock_scanner
    unregister_scanner = Mock()
    mock_manager = Mock()
    mock_manager.async_register_scanner = Mock(return_value=unregister_scanner)

    with patch("bleak_esphome.connection_manager.ReconnectLogic"):
        manager = APIConnectionManager(config)

    manager._cli = Mock()
    manager._cli.device_info = AsyncMock(return_value=Mock(name="device_info"))

    with (
        patch(
            "bleak_esphome.connect_scanner", return_value=mock_client_data
        ) as mock_connect_scanner,
        patch(
            "bleak_esphome.connection_manager.habluetooth.get_manager",
            return_value=mock_manager,
        ),
    ):
        await manager._on_connect()

    mock_connect_scanner.assert_called_once_with(
        manager._cli, manager._cli.device_info.return_value, True
    )
    mock_scanner.async_setup.assert_called_once_with()
    mock_manager.async_register_scanner.assert_called_once_with(mock_scanner)
    assert manager._unregister_scanner is unregister_scanner
    assert manager._start_future.done()
    assert manager._start_future.result() is None


@pytest.mark.asyncio
async def test_on_connect_with_already_done_future_does_not_raise() -> None:
    """Re-entering ``_on_connect`` after the future resolved is a no-op for it.

    On reconnection, ``_on_connect`` may fire again. The future is one-shot
    and must not raise ``InvalidStateError`` when already done.
    """
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch("bleak_esphome.connection_manager.ReconnectLogic"):
        manager = APIConnectionManager(config)

    manager._start_future.set_result(None)
    manager._cli = Mock()
    manager._cli.device_info = AsyncMock(return_value=Mock())

    mock_client_data = Mock()
    mock_client_data.scanner = Mock()

    with (
        patch("bleak_esphome.connect_scanner", return_value=mock_client_data),
        patch(
            "bleak_esphome.connection_manager.habluetooth.get_manager",
            return_value=MagicMock(),
        ),
    ):
        # Must not raise InvalidStateError on the already-resolved future.
        await manager._on_connect()


@pytest.mark.asyncio
async def test_on_disconnect_unregisters_scanner_when_registered() -> None:
    """``_on_disconnect`` calls the unregister callback and clears it."""
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch("bleak_esphome.connection_manager.ReconnectLogic"):
        manager = APIConnectionManager(config)

    unregister = Mock()
    manager._unregister_scanner = unregister

    await manager._on_disconnect(expected_disconnect=True)

    unregister.assert_called_once_with()
    assert manager._unregister_scanner is None


@pytest.mark.asyncio
async def test_on_disconnect_when_no_scanner_registered_is_noop() -> None:
    """``_on_disconnect`` is safe when no scanner was registered yet."""
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch("bleak_esphome.connection_manager.ReconnectLogic"):
        manager = APIConnectionManager(config)

    assert manager._unregister_scanner is None
    await manager._on_disconnect(expected_disconnect=False)
    assert manager._unregister_scanner is None


@pytest.mark.asyncio
async def test_stop_unregisters_scanner_if_registered() -> None:
    """``stop()`` calls the scanner unregister callback if one is set."""
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch(
        "bleak_esphome.connection_manager.ReconnectLogic"
    ) as mock_reconnect_logic_cls:
        mock_reconnect_logic = mock_reconnect_logic_cls.return_value
        mock_reconnect_logic.stop = AsyncMock()
        manager = APIConnectionManager(config)
        manager._cli = Mock()
        manager._cli.disconnect = AsyncMock()
        unregister = Mock()
        manager._unregister_scanner = unregister
        # Mark the start future done so stop() doesn't cancel it.
        manager._start_future.set_result(None)

        await manager.stop()

    unregister.assert_called_once_with()
    assert manager._unregister_scanner is None
    mock_reconnect_logic.stop.assert_awaited_once_with()
    manager._cli.disconnect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stop_without_scanner_does_not_call_unregister() -> None:
    """``stop()`` is a no-op for the scanner branch when nothing is registered."""
    config: ESPHomeDeviceConfig = {"address": "test.local", "noise_psk": None}

    with patch(
        "bleak_esphome.connection_manager.ReconnectLogic"
    ) as mock_reconnect_logic_cls:
        mock_reconnect_logic = mock_reconnect_logic_cls.return_value
        mock_reconnect_logic.stop = AsyncMock()
        manager = APIConnectionManager(config)
        manager._cli = Mock()
        manager._cli.disconnect = AsyncMock()
        manager._start_future.set_result(None)

        await manager.stop()

    assert manager._unregister_scanner is None
