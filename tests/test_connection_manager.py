"""Tests for ``bleak_esphome.connection_manager``."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

from bleak_esphome.connection_manager import (
    APIConnectionManager,
    ESPHomeDeviceConfig,
    ESPHomeStartAborted,
)


@pytest.fixture
def config() -> ESPHomeDeviceConfig:
    """Return a minimal device config used across tests."""
    return {"address": "test.local", "noise_psk": None}


@pytest_asyncio.fixture
async def conn_manager(config: ESPHomeDeviceConfig) -> APIConnectionManager:
    """Build an ``APIConnectionManager`` under a patched ``ReconnectLogic``."""
    with patch("bleak_esphome.connection_manager.ReconnectLogic"):
        return APIConnectionManager(config)


@pytest_asyncio.fixture
async def conn_manager_with_mocked_reconnect(
    config: ESPHomeDeviceConfig,
) -> AsyncIterator[tuple[APIConnectionManager, Mock, AsyncMock]]:
    """
    Yield ``(manager, mock_reconnect_logic, mock_disconnect)`` for ``stop()`` tests.

    The manager has its ``_cli.disconnect`` patched with ``AsyncMock`` and a
    resolved ``_start_future`` so ``stop()`` does not cancel it.
    """
    with patch(
        "bleak_esphome.connection_manager.ReconnectLogic"
    ) as mock_reconnect_logic_cls:
        mock_reconnect_logic = mock_reconnect_logic_cls.return_value
        mock_reconnect_logic.stop = AsyncMock()
        mgr = APIConnectionManager(config)
        mgr._start_future.set_result(None)
        mock_disconnect = AsyncMock()
        with patch.object(mgr._cli, "disconnect", mock_disconnect):
            yield mgr, mock_reconnect_logic, mock_disconnect


@pytest.fixture
def patched_scanner_wiring() -> Iterator[tuple[Mock, Mock]]:
    """Patch ``connect_scanner`` and ``habluetooth.get_manager`` together."""
    with (
        patch("bleak_esphome.connect_scanner") as connect_scanner_mock,
        patch(
            "bleak_esphome.connection_manager.habluetooth.get_manager"
        ) as get_manager_mock,
    ):
        yield connect_scanner_mock, get_manager_mock


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
async def test_on_connect_registers_scanner_and_resolves_start(
    conn_manager: APIConnectionManager,
    patched_scanner_wiring: tuple[Mock, Mock],
) -> None:
    """
    ``_on_connect`` wires the scanner and unblocks a pending ``start()``.

    The reconnect callback fetches device info, builds a scanner via
    ``bleak_esphome.connect_scanner``, sets it up, registers it with the
    habluetooth manager, and resolves ``_start_future`` so a waiting
    ``start()`` returns.
    """
    mock_scanner = Mock()
    mock_client_data = Mock()
    mock_client_data.scanner = mock_scanner
    mock_client_data.disconnect_callbacks = set()
    mock_client_data.unsubscribe_callbacks = []
    unregister_scanner = Mock()
    mock_habluetooth_manager = Mock()
    mock_habluetooth_manager.async_register_scanner = Mock(
        return_value=unregister_scanner
    )

    connect_scanner_mock, get_manager_mock = patched_scanner_wiring
    connect_scanner_mock.return_value = mock_client_data
    get_manager_mock.return_value = mock_habluetooth_manager

    conn_manager._cli = Mock()
    conn_manager._cli.device_info = AsyncMock(return_value=Mock(name="device_info"))

    await conn_manager._on_connect()

    connect_scanner_mock.assert_called_once_with(
        conn_manager._cli, conn_manager._cli.device_info.return_value, True
    )
    mock_scanner.async_setup.assert_called_once_with()
    mock_habluetooth_manager.async_register_scanner.assert_called_once_with(
        mock_scanner
    )
    assert conn_manager._unregister_scanner is unregister_scanner
    assert conn_manager._disconnect_callbacks is mock_client_data.disconnect_callbacks
    assert conn_manager._unsubscribe_callbacks is mock_client_data.unsubscribe_callbacks
    assert conn_manager._start_future.done()
    assert conn_manager._start_future.result() is None


@pytest.mark.asyncio
async def test_on_connect_with_already_done_future_does_not_raise(
    conn_manager: APIConnectionManager,
    patched_scanner_wiring: tuple[Mock, Mock],
) -> None:
    """
    Re-entering ``_on_connect`` after the future resolved is a no-op for it.

    On reconnection, ``_on_connect`` may fire again. The future is one-shot
    and must not raise ``InvalidStateError`` when already done.
    """
    conn_manager._start_future.set_result(None)
    conn_manager._cli = Mock()
    conn_manager._cli.device_info = AsyncMock(return_value=Mock())

    mock_client_data = Mock()
    mock_client_data.scanner = Mock()
    mock_client_data.disconnect_callbacks = set()
    mock_client_data.unsubscribe_callbacks = []

    connect_scanner_mock, get_manager_mock = patched_scanner_wiring
    connect_scanner_mock.return_value = mock_client_data
    get_manager_mock.return_value = MagicMock()

    # Must not raise InvalidStateError on the already-resolved future.
    await conn_manager._on_connect()


@pytest.mark.asyncio
async def test_on_disconnect_unregisters_scanner_when_registered(
    conn_manager: APIConnectionManager,
) -> None:
    """``_on_disconnect`` calls the unregister callback and clears it."""
    unregister = Mock()
    conn_manager._unregister_scanner = unregister

    await conn_manager._on_disconnect(expected_disconnect=True)

    unregister.assert_called_once_with()
    # ``cast`` re-widens the attribute type that mypy narrowed to ``Mock``
    # after the earlier assignment so ``is None`` is not flagged unreachable.
    assert cast(Callable[[], None] | None, conn_manager._unregister_scanner) is None


@pytest.mark.asyncio
async def test_on_disconnect_when_no_scanner_registered_is_noop(
    conn_manager: APIConnectionManager,
) -> None:
    """``_on_disconnect`` is safe when no scanner was registered yet."""
    assert conn_manager._unregister_scanner is None
    await conn_manager._on_disconnect(expected_disconnect=False)
    assert conn_manager._unregister_scanner is None


@pytest.mark.asyncio
async def test_on_disconnect_fires_client_data_disconnect_callbacks(
    conn_manager: APIConnectionManager,
) -> None:
    """
    ``_on_disconnect`` invokes every registered ``ESPHomeClient`` disconnect cb.

    Each active BLE client (``ESPHomeClient``) registers a disconnect callback
    in ``client_data.disconnect_callbacks`` so that when the ESP drops, it can
    tear down its state and notify bleak callers. The manager must fire them.
    """
    cb_one = Mock()
    cb_two = Mock()
    conn_manager._disconnect_callbacks = {cb_one, cb_two}

    await conn_manager._on_disconnect(expected_disconnect=False)

    cb_one.assert_called_once_with()
    cb_two.assert_called_once_with()
    assert conn_manager._disconnect_callbacks is None


@pytest.mark.asyncio
async def test_on_disconnect_tolerates_callback_self_removal(
    conn_manager: APIConnectionManager,
) -> None:
    """
    Firing a callback that mutates the set must not raise.

    Real ``ESPHomeClient`` callbacks discard themselves from
    ``disconnect_callbacks`` during ``_async_disconnected_cleanup``, so the
    manager must iterate a snapshot rather than the live set.
    """
    callbacks: set[Callable[[], None]] = set()

    def self_removing() -> None:
        callbacks.discard(self_removing)

    callbacks.add(self_removing)
    conn_manager._disconnect_callbacks = callbacks

    # Should not raise ``RuntimeError: set changed size during iteration``.
    await conn_manager._on_disconnect(expected_disconnect=True)
    assert conn_manager._disconnect_callbacks is None


@pytest.mark.asyncio
async def test_on_disconnect_invokes_unsubscribe_callbacks(
    conn_manager: APIConnectionManager,
) -> None:
    """
    ``_on_disconnect`` tears down every APIClient subscription captured.

    Without this, subscriptions on the persistent ``APIClient`` accumulate on
    every reconnect — old scanners keep receiving advertisement callbacks and
    old devices keep receiving slot-update callbacks.
    """
    unsub_one = Mock()
    unsub_two = Mock()
    conn_manager._unsubscribe_callbacks = [unsub_one, unsub_two]

    await conn_manager._on_disconnect(expected_disconnect=False)

    unsub_one.assert_called_once_with()
    unsub_two.assert_called_once_with()
    assert conn_manager._unsubscribe_callbacks is None


@pytest.mark.asyncio
async def test_on_disconnect_without_unsubscribe_callbacks_is_noop(
    conn_manager: APIConnectionManager,
) -> None:
    """``_on_disconnect`` is safe when no subscriptions were captured yet."""
    assert conn_manager._unsubscribe_callbacks is None
    await conn_manager._on_disconnect(expected_disconnect=False)
    assert conn_manager._unsubscribe_callbacks is None


@pytest.mark.asyncio
async def test_stop_unregisters_scanner_if_registered(
    conn_manager_with_mocked_reconnect: tuple[APIConnectionManager, Mock, AsyncMock],
) -> None:
    """``stop()`` calls the scanner unregister callback if one is set."""
    manager, mock_reconnect_logic, mock_disconnect = conn_manager_with_mocked_reconnect
    unregister = Mock()
    manager._unregister_scanner = unregister

    await manager.stop()

    unregister.assert_called_once_with()
    mock_reconnect_logic.stop.assert_awaited_once_with()
    mock_disconnect.assert_awaited_once_with()
    # ``cast`` re-widens the attribute type that mypy narrowed to ``Mock``
    # after the earlier assignment so ``is None`` is not flagged unreachable.
    assert cast(Callable[[], None] | None, manager._unregister_scanner) is None


@pytest.mark.asyncio
async def test_stop_without_scanner_does_not_call_unregister(
    conn_manager_with_mocked_reconnect: tuple[APIConnectionManager, Mock, AsyncMock],
) -> None:
    """``stop()`` is a no-op for the scanner branch when nothing is registered."""
    manager, mock_reconnect_logic, mock_disconnect = conn_manager_with_mocked_reconnect

    await manager.stop()

    assert manager._unregister_scanner is None
    mock_reconnect_logic.stop.assert_awaited_once_with()
    mock_disconnect.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stop_invokes_unsubscribe_callbacks(
    conn_manager_with_mocked_reconnect: tuple[APIConnectionManager, Mock, AsyncMock],
) -> None:
    """
    ``stop()`` tears down captured subscriptions before the unregister branch.

    Symmetric with how the scanner unregister branch is handled in both
    ``_on_disconnect`` and ``stop()`` — protects against the case where
    ``stop()`` is reached without ``_on_disconnect`` having fired.
    """
    manager, _logic, _disconnect = conn_manager_with_mocked_reconnect
    unsub = Mock()
    manager._unsubscribe_callbacks = [unsub]

    await manager.stop()

    unsub.assert_called_once_with()
    assert manager._unsubscribe_callbacks is None
