"""Tests for ``bleak_esphome.connection_manager``."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

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
